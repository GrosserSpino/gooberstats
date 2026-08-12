#!/usr/bin/env python3
import argparse, csv, json, re, shutil
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN=ZoneInfo('Europe/Berlin')

def completed_month_dirs(root: Path, include_current=False):
    current = date.today().strftime('%Y-%m')
    return sorted((p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}', p.name) and (p.name <= current if include_current else p.name < current)), key=lambda p:p.name)

def number(value, default=0, as_int=False):
    try:
        parsed=float(str(value or '').rstrip('%'))
        return int(parsed) if as_int else parsed
    except (TypeError, ValueError):
        return default

def month_aliases(tools_root: Path, month_id: str):
    path=tools_root/'data'/'player_name_timeline.csv'
    aliases=defaultdict(list)
    if not path.exists(): return aliases
    start=f'{month_id}-01'
    end=(datetime.strptime(start,'%Y-%m-%d')+timedelta(days=32)).replace(day=1).date().isoformat()
    with path.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if (row.get('valid_to','')[:10] < start or row.get('valid_from','')[:10] >= end): continue
            pid=row.get('player_id',''); name=(row.get('display_name') or '').strip()
            if name and name.casefold() not in {x.casefold() for x in aliases[pid]}: aliases[pid].append(name)
    return aliases

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tools-root',type=Path,required=True)
    ap.add_argument('--month',help='Export a specific month (YYYY-MM), including the current unfinished month.')
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'docs'/'data')
    args=ap.parse_args(); out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    legacy_index=out/'players.json'
    if legacy_index.exists(): legacy_index.unlink()
    legacy_profiles=out/'profiles'
    if legacy_profiles.exists(): shutil.rmtree(legacy_profiles)
    tools_root=args.tools_root.resolve()
    months=completed_month_dirs(tools_root/'Leaderboards Monthly Top100',include_current=True)
    if not months: raise SystemExit('No completed monthly leaderboard found.')
    month=next((item for item in months if item.name==args.month),None) if args.month else months[-1]
    if month is None: raise SystemExit(f'Month not found: {args.month}')
    csv_path=month/'assets.csv'
    if not csv_path.exists(): csv_path=month/'leaderboard.csv'
    with csv_path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))[:50]
    aliases=month_aliases(tools_root,month.name)
    players=[]
    for r in rows:
        pid=r['player_id']; name=r['display_name']
        aka=[x for x in aliases[pid] if x.casefold()!=name.casefold()]
        players.append({'rank':int(r['rank']),'id':pid,'name':name,'aliases':aka,'country':r.get('country',''),'wins':number(r.get('monthly_wins',r.get('wins')),as_int=True),'games':number(r.get('monthly_games',r.get('games')),as_int=True),'deaths':number(r.get('monthly_deaths'),as_int=True),'winrate':number(r.get('monthly_winrate',r.get('winrate'))),'deathrate':number(r.get('monthly_deathrate')),'performanceRate':number(r.get('skillrate'),default=None),'performanceGames':number(r.get('skill_games'),as_int=True),'alltime':{'level':number(r.get('level'),default=None,as_int=True),'games':number(r.get('total_games'),default=None,as_int=True),'wins':number(r.get('total_wins'),default=None,as_int=True),'deaths':number(r.get('total_deaths'),default=None,as_int=True),'winstreak':None},'cosmetics':{key:r.get(key,'') for key in ('hat','suit','body','hand','color')}})
    label=datetime.strptime(month.name,'%Y-%m').strftime('%B %Y')
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),'month':month.name,'monthLabel':label,'current':month.name==date.today().strftime('%Y-%m'),'source':str(csv_path.relative_to(tools_root)).replace('\\','/'),'players':players}
    top_ids={p['id'] for p in players}
    difficulties={h:0.0 for h in range(24)}
    difficulty_path=tools_root/'Hourly Difficulty'/'global.json'
    if difficulty_path.exists():
        difficulty_doc=json.loads(difficulty_path.read_text(encoding='utf-8'))
        difficulties.update({int(r['hour']):float(r['difficulty_relative_pct']) for r in difficulty_doc.get('hours',[])})
    hourly=defaultdict(lambda:defaultdict(lambda:{'games':0,'wins':0,'dates':set()}))
    player_windows=defaultdict(list)
    top50_windows=defaultdict(lambda:{'games':0,'wins':0})
    coverage_windows={}
    coverage_dates=set()
    coverage_by_hour=defaultdict(set)
    delta_root=args.tools_root.resolve()/'hourly_deltas'
    for day_dir in sorted(delta_root.glob(f'{month.name}-*')):
        for delta in sorted(day_dir.glob('*.csv')):
            with delta.open(encoding='utf-8-sig',newline='') as f: delta_rows=list(csv.DictReader(f))
            if not delta_rows: continue
            time_text=(delta_rows[0].get('time') or '').strip()
            if '-' not in time_text: continue
            start_text,end_text=[x.strip() for x in time_text.split('-',1)]
            try:
                start_dt=datetime.fromisoformat(f'{day_dir.name}T{start_text}:00')
                end_dt=datetime.fromisoformat(f'{day_dir.name}T{end_text}:00')
            except ValueError: continue
            if end_dt<=start_dt: end_dt+=timedelta(days=1)
            minutes=(end_dt-start_dt).total_seconds()/60
            if not (50<=minutes<=70 and start_dt.minute<=15 and end_dt.minute<=20): continue
            hour=start_dt.hour; coverage_dates.add(day_dir.name); coverage_by_hour[hour].add(day_dir.name)
            timestamp=start_dt.replace(tzinfo=BERLIN).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
            coverage_windows[timestamp]={'timestamp':timestamp,'difficulty':round(difficulties[hour],1)}
            for row in delta_rows:
                pid=(row.get('id') or row.get('player_id') or '').strip()
                if pid not in top_ids: continue
                games=int(float(row.get('games') or 0)); wins=int(float(row.get('wins') or 0))
                hourly[pid][hour]['games']+=games; hourly[pid][hour]['wins']+=wins
                hourly[pid][hour]['dates'].add(day_dir.name)
                if games>0:
                    player_windows[pid].append({'timestamp':timestamp,'games':games,'wins':wins,'difficulty':round(difficulties[hour],1)})
                    top50_windows[timestamp]['games']+=games
                    top50_windows[timestamp]['wins']+=wins
    monthly_dir=out/'monthly-profiles'; monthly_dir.mkdir(exist_ok=True)
    for old in monthly_dir.glob('*.json'): old.unlink()
    highest_hour=max((item['games'] for pid in top_ids for item in hourly[pid].values()),default=0)
    activity_scale_max=max(25,int(math.ceil(highest_hour/25))*25)
    chart_rates=[]
    for pid in top_ids:
        for hour in range(24):
            window=[hourly[pid][(hour+offset)%24] for offset in (-2,-1,0,1,2)]
            games=sum(item['games'] for item in window)
            wins=sum(item['wins'] for item in window)
            if hourly[pid][hour]['games']>=15 and games>=30: chart_rates.append(100*wins/games)
    performance_scale_min=max(0,10*math.floor(min(chart_rates,default=0)/10))
    performance_scale_max=min(100,10*math.ceil(max(chart_rates,default=100)/10))
    if performance_scale_max-performance_scale_min<40:
        performance_scale_min=max(0,performance_scale_min-10)
        performance_scale_max=min(100,performance_scale_max+10)
    payload['performanceScaleMin']=performance_scale_min
    payload['performanceScaleMax']=performance_scale_max
    payload['top50Windows']=[{'timestamp':timestamp,**values} for timestamp,values in sorted(top50_windows.items())]
    (out/'biggest-winners.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for player in players:
        pid=player['id']; rows=[]; adjusted_wins=0.0; performance_games=0
        for hour in range(24):
            item=hourly[pid][hour]; games=item['games']; wins=item['wins']; days=len(coverage_by_hour[hour])
            factor=1+difficulties[hour]/100
            if games>0 and factor>0: adjusted_wins+=wins/factor; performance_games+=games
            rows.append({'hour':hour,'games':games,'wins':wins,'winrate':round(wins/games*100,2) if games else None,'gamesPerCoveredDay':round(games/days,3) if days else 0,'difficulty':round(difficulties[hour],1),'coveredDays':days})
        lobby_factor=round(player['performanceRate']/player['winrate'],3) if player['performanceRate'] is not None and player['winrate'] else None
        profile={**player,'month':month.name,'monthLabel':label,'sourceTimeZone':'Europe/Berlin','activityScaleMax':activity_scale_max,'performanceScaleMin':performance_scale_min,'performanceScaleMax':performance_scale_max,'difficultyScaleMin':-30,'difficultyScaleMax':30,'monthlyWinrateValue':round(player['wins']/player['games']*100,2) if player['games'] else 0,'lobbyDifficulty':lobby_factor,'performanceRate':round(adjusted_wins/performance_games*100,2) if performance_games else player['performanceRate'],'performanceGames':performance_games or player['performanceGames'],'hourlyCoverageStart':min(coverage_dates) if coverage_dates else None,'hourlyCoverageEnd':max(coverage_dates) if coverage_dates else None,'coverageWindows':list(coverage_windows.values()),'hourlyWindows':player_windows[pid],'hourly':rows,'badges':[]}
        (monthly_dir/f'{pid}.json').write_text(json.dumps(profile,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    # Stable, reusable badge records. The active calendar month never awards a badge.
    badge_map=defaultdict(list)
    current_id=date.today().strftime('%Y-%m')
    for badge_month in (p for p in months if p.name < current_id):
        badge_csv=badge_month/'assets.csv'
        if not badge_csv.exists(): badge_csv=badge_month/'leaderboard.csv'
        if not badge_csv.exists(): continue
        with badge_csv.open(encoding='utf-8-sig',newline='') as f: badge_rows=list(csv.DictReader(f))[:10]
        for row in badge_rows:
            record={'month':badge_month.name,'monthLabel':datetime.strptime(badge_month.name,'%Y-%m').strftime('%B %Y'),'rank':number(row.get('rank'),as_int=True),'wins':number(row.get('monthly_wins',row.get('wins')),as_int=True)}
            badge_map[row['player_id']].append(record)
    (out/'badges.json').write_text(json.dumps(badge_map,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for profile_path in monthly_dir.glob('*.json'):
        doc=json.loads(profile_path.read_text(encoding='utf-8')); doc['badges']=sorted(badge_map.get(doc['id'],[]),key=lambda x:x['month'],reverse=True)
        profile_path.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    archive=out/'months'/month.name
    archive.mkdir(parents=True,exist_ok=True)
    shutil.copy2(out/'biggest-winners.json',archive/'biggest-winners.json')
    archive_profiles=archive/'monthly-profiles'
    if archive_profiles.exists(): shutil.rmtree(archive_profiles)
    shutil.copytree(monthly_dir,archive_profiles)
    print(f'Exported {len(players)} monthly winner profiles for {label}; hourly coverage {min(coverage_dates) if coverage_dates else "none"} to {max(coverage_dates) if coverage_dates else "none"}.')
if __name__=='__main__': main()
