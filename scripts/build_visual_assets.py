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
    for month in sorted((tools_root/'Leaderboards Monthly Top100').glob('????-??')):
        try: label=datetime.strptime(month.name,'%Y-%m').strftime('%B %Y')
        except ValueError: label=month.name
        render_race_text(font_path,label,1200).save(output/f'hero-{month.name}.png',optimize=True)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tools-root',type=Path,required=True); ap.add_argument('--generator-root',type=Path); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--hero-only',action='store_true'); args=ap.parse_args()
    tools_root=args.tools_root.resolve(); output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    render_hero_assets(tools_root,output,output/'LuckiestGuy-Regular.ttf')
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
    for pid,row in players.items():
        signature=[row.get('hat',''),row.get('suit',''),row.get('hand',''),row.get('color','')]
        target=goober_dir/f'{pid}.png'; manifest['goobers'][pid]=signature
        if old_manifest.get('goobers',{}).get(pid)==signature and target.exists(): continue
        image=crop(race.generate_goober(*signature)); image.thumbnail((360,360),Image.Resampling.LANCZOS); image.save(target,optimize=True); rendered_goobers+=1
    countries={row.get('country','').upper() for row in players.values() if row.get('country')}
    for country in countries:
        target=flag_dir/f'{country}.png'; manifest['flags'][country]=[96,96]
        if old_manifest.get('flags',{}).get(country)==[96,96] and target.exists(): continue
        image=race.load_flag_image(country,(96,96))
        if image is not None: image.save(target,optimize=True); rendered_flags+=1
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'Rendered {rendered_goobers} changed goobers and {rendered_flags} changed flags; reused the rest.')
if __name__=='__main__': main()
