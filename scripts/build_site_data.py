#!/usr/bin/env python3
import argparse, csv, json, re, shutil
from datetime import date, datetime, timezone
from pathlib import Path

def completed_month_dirs(root: Path):
    current = date.today().strftime('%Y-%m')
    return sorted((p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}', p.name) and p.name < current), key=lambda p:p.name)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tools-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'docs'/'data')
    args=ap.parse_args(); out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    source=args.tools_root.resolve()/'Goober Profiles'/'public'/'data'
    if not (source/'players.json').exists(): raise SystemExit('Run Goober Profiles/build_profiles.py first.')
    shutil.copy2(source/'players.json',out/'players.json')
    target=out/'profiles'; target.mkdir(exist_ok=True)
    for old in target.glob('*.json'): old.unlink()
    for profile in (source/'profiles').glob('*.json'): shutil.copy2(profile,target/profile.name)
    months=completed_month_dirs(args.tools_root.resolve()/'Leaderboards Monthly Top100')
    if not months: raise SystemExit('No completed monthly leaderboard found.')
    month=months[-1]; csv_path=month/'assets.csv'
    if not csv_path.exists(): csv_path=month/'leaderboard.csv'
    with csv_path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))[:50]
    players=[]
    for r in rows:
        players.append({'rank':int(r['rank']),'id':r['player_id'],'name':r['display_name'],'country':r.get('country',''),'wins':int(r.get('monthly_wins',r.get('wins',0))),'games':int(r.get('monthly_games',r.get('games',0))),'winrate':r.get('monthly_winrate',r.get('winrate',''))})
    label=datetime.strptime(month.name,'%Y-%m').strftime('%B %Y')
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),'month':month.name,'monthLabel':label,'source':str(csv_path.relative_to(args.tools_root.resolve())).replace('\\','/'),'players':players}
    (out/'biggest-winners.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'Exported {len(players)} winners for {label} and {len(list(target.glob("*.json")))} profiles.')
if __name__=='__main__': main()
