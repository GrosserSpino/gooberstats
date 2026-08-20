#!/usr/bin/env python3
import argparse, csv, importlib.util, json, os
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def load_race(generator_root):
    os.environ['GOOBER_RACE_TESTING']='1'
    os.environ['GOOBER_RACE_HOME']=str(generator_root/'.website-runtime')
    spec=importlib.util.spec_from_file_location('goober_race',generator_root/'src'/'race.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def crop(image):
    box=image.getbbox()
    return image.crop(box) if box else image

def normalize_goober(image):
    """Normalize from the generator canvas so its shared eye anchor never moves."""
    source_width,source_height=380,460
    viewport=image.crop((0,0,min(source_width,image.width),min(source_height,image.height)))
    target_width=round(source_width*360/source_height)
    viewport=viewport.resize((target_width,360),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(360,360),(0,0,0,0))
    canvas.alpha_composite(viewport,((360-viewport.width)//2,360-viewport.height))
    return canvas

def render_profile_card_modules(output):
    """Split the neutral master so badge growth cannot distort the profile or stats."""
    source=output/'profile-card-master-silver.png'
    if not source.exists(): return
    image=Image.open(source).convert('RGBA')
    cuts={
        'profile-card-top.png':(0,0,image.width,735),
        'profile-card-stats.png':(0,725,image.width,1315),
        'profile-card-badges.png':(0,1305,image.width,image.height),
    }
    for name,box in cuts.items(): image.crop(box).save(output/name,optimize=True)

def render_race_text(font_path,text,max_width):
    size=100
    measure=ImageDraw.Draw(Image.new('RGBA',(10,10),(0,0,0,0)))
    while size>36:
        font=ImageFont.truetype(font_path,size)
        bbox=measure.textbbox((0,0),text,font=font,stroke_width=12)
        if bbox[2]-bbox[0]<=max_width: break
        size-=4
    outer=(75,178,255,255); inner=(0,114,188,255); fill=(255,255,255,255); highlight=(225,245,255,170)
    outer_w=max(10,int(round(size*.16))); inner_w=max(7,int(round(size*.09))); pad=max(80,outer_w*5)
    bbox=measure.textbbox((0,0),text,font=font,stroke_width=outer_w)
    layer=Image.new('RGBA',(bbox[2]-bbox[0]+pad*2,bbox[3]-bbox[1]+pad*2),(0,0,0,0))
    draw=ImageDraw.Draw(layer); xy=(pad-bbox[0],pad-bbox[1])
    draw.text(xy,text,font=font,fill=outer,stroke_width=outer_w,stroke_fill=outer)
    draw.text(xy,text,font=font,fill=inner,stroke_width=inner_w,stroke_fill=inner)
    draw.text(xy,text,font=font,fill=fill,stroke_width=0)
    draw.text((xy[0]-2,xy[1]-max(2,int(size*.045))),text,font=font,fill=highlight,stroke_width=0)
    return crop(layer)

def render_hero_assets(tools_root,output,font_path):
    render_race_text(font_path,'BIGGEST WINNERS',2000).save(output/'hero-biggest-winners.png',optimize=True)
    render_race_text(font_path,'ALLTIME',1200).save(output/'hero-alltime.png',optimize=True)
    for month in sorted((tools_root/'Leaderboards Monthly Top100').glob('????-??')):
        try: label=datetime.strptime(month.name,'%Y-%m').strftime('%B %Y')
        except ValueError: label=month.name
        render_race_text(font_path,label,1200).save(output/f'hero-{month.name}.png',optimize=True)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tools-root',type=Path,required=True); ap.add_argument('--generator-root',type=Path); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--hero-only',action='store_true'); args=ap.parse_args()
    tools_root=args.tools_root.resolve(); output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    render_hero_assets(tools_root,output,output/'LuckiestGuy-Regular.ttf')
    render_profile_card_modules(output)
    if args.hero_only: return
    if not args.generator_root: ap.error('--generator-root is required unless --hero-only is used')
    race=load_race(args.generator_root.resolve()); goober_dir=output/'goobers'; flag_dir=output/'flags'; goober_dir.mkdir(parents=True,exist_ok=True); flag_dir.mkdir(parents=True,exist_ok=True)
    manifest_path=output/'visual-manifest.json'
    try: old_manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError): old_manifest={}
    manifest={'goobers':{},'flags':{}}; rendered_goobers=rendered_flags=0; players={}
    for month in sorted((tools_root/'Leaderboards Monthly Top100').glob('????-??')):
        path=month/'assets.csv'
        if not path.exists(): continue
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row in list(csv.DictReader(f))[:50]: players[row['player_id']]=row
    try:
        alltime=json.loads((output.parent/'data'/'alltime.json').read_text(encoding='utf-8'))
        for row in alltime.get('players',[]):
            cosmetics=row.get('cosmetics',{})
            players[row['id']]={**row,**cosmetics}
    except (FileNotFoundError,json.JSONDecodeError,KeyError):
        pass
    method_countries={}
    try:
        method=json.loads((output.parent/'data'/'method.json').read_text(encoding='utf-8'))
        hourly={hour:{} for hour in range(24)}
        for window in method.get('hourWindows',[]):
            hour=datetime.fromisoformat(window['timestamp'].replace('Z','+00:00')).hour
            for p in window.get('players',[]):
                stats=hourly[hour].setdefault(p['id'],{'games':0,'wins':0}); stats['games']+=p['games']; stats['wins']+=p.get('wins',0)
        method_ids={pid for totals in hourly.values() for pid,stats in sorted(totals.items(),key=lambda item:(-item[1]['wins'],-item[1]['games'],-item[1]['wins']/item[1]['games'],item[0]))[:5]}
        method_ids.update(p['id'] for record in method.get('hardestRecords',[]) for p in record.get('participants',[]) if p.get('id'))
        method_countries={p['id']:p.get('country','') for record in method.get('hardestRecords',[]) for p in record.get('participants',[]) if p.get('id')}
    except (FileNotFoundError,json.JSONDecodeError,KeyError): method_ids=set()
    snapshots=sorted((tools_root/'daily_snapshots').glob('*.csv'))
    if snapshots and method_ids:
        unresolved=set(method_ids)
        for snapshot in reversed(snapshots):
            if not unresolved: break
            with snapshot.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    pid=row.get('player_id') or row.get('id')
                    if pid in unresolved:
                        players[pid]={**row,'country':row.get('country') or method_countries.get(pid,'')}; unresolved.remove(pid)
    for pid,row in players.items():
        signature=[row.get('hat',''),row.get('suit',''),row.get('hand',''),row.get('color','')]
        cache_signature=signature+['fixed-eye-anchor-v2']
        target=goober_dir/f'{pid}.png'; manifest['goobers'][pid]=cache_signature
        if old_manifest.get('goobers',{}).get(pid)==cache_signature and target.exists(): continue
        normalize_goober(race.generate_goober(*signature)).save(target,optimize=True); rendered_goobers+=1
    countries={row.get('country','').upper() for row in players.values() if row.get('country')}
    for country in countries:
        target=flag_dir/f'{country}.png'; manifest['flags'][country]=[96,96]
        if old_manifest.get('flags',{}).get(country)==[96,96] and target.exists(): continue
        image=race.load_flag_image(country,(96,96))
        if image is not None: image.save(target,optimize=True); rendered_flags+=1
    unknown_target=flag_dir/'UNKNOWN.png'
    unknown_source=args.generator_root.resolve()/'assets'/'kenny-flags'/'special_unavailable.png'
    if unknown_source.exists():
        Image.open(unknown_source).convert('RGBA').resize((96,96),Image.Resampling.LANCZOS).save(unknown_target,optimize=True)
        manifest['flags']['UNKNOWN']=[96,96]
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'Rendered {rendered_goobers} changed goobers and {rendered_flags} changed flags; reused the rest.')
if __name__=='__main__': main()
