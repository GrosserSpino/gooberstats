#!/usr/bin/env python3
import argparse, csv, importlib.util, json, os
from pathlib import Path
from PIL import Image

def load_race(generator_root):
    os.environ['GOOBER_RACE_TESTING']='1'
    os.environ['GOOBER_RACE_HOME']=str(generator_root/'.website-runtime')
    spec=importlib.util.spec_from_file_location('goober_race',generator_root/'src'/'race.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def crop(image):
    box=image.getbbox()
    return image.crop(box) if box else image

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tools-root',type=Path,required=True); ap.add_argument('--generator-root',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    race=load_race(args.generator_root.resolve()); output=args.output.resolve(); goober_dir=output/'goobers'; flag_dir=output/'flags'; goober_dir.mkdir(parents=True,exist_ok=True); flag_dir.mkdir(parents=True,exist_ok=True)
    manifest_path=output/'visual-manifest.json'
    try: old_manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError): old_manifest={}
    manifest={'goobers':{},'flags':{}}; rendered_goobers=rendered_flags=0
    players={}
    for month in sorted((args.tools_root/'Leaderboards Monthly Top100').glob('????-??')):
        path=month/'assets.csv'
        if not path.exists(): continue
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row in list(csv.DictReader(f))[:50]: players[row['player_id']]=row
    for pid,row in players.items():
        signature=[row.get('hat',''),row.get('suit',''),row.get('hand',''),row.get('color','')]
        target=goober_dir/f'{pid}.png'; manifest['goobers'][pid]=signature
        if old_manifest.get('goobers',{}).get(pid)==signature and target.exists(): continue
        image=crop(race.generate_goober(*signature))
        image.thumbnail((360,360),Image.Resampling.LANCZOS); image.save(target,optimize=True); rendered_goobers+=1
    countries={row.get('country','').upper() for row in players.values() if row.get('country')}
    for country in countries:
        target=flag_dir/f'{country}.png'; manifest['flags'][country]=[96,96]
        if old_manifest.get('flags',{}).get(country)==[96,96] and target.exists(): continue
        image=race.load_flag_image(country,(96,96))
        if image is not None: image.save(target,optimize=True); rendered_flags+=1
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'Rendered {rendered_goobers} changed goobers and {rendered_flags} changed flags; reused the rest.')
if __name__=='__main__': main()
