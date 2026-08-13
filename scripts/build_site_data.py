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

def historical_badge_rows(tools_root: Path, current_id: str, output_dir: Path):
    results=[]; authoritative=set(); leaderboards=[]
    if output_dir.exists(): shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)

    def save_leaderboard(month_id, start, end, rows, estimated, source):
        ranked=[]
        for rank,row in enumerate(rows[:50],1):
            games=number(row.get('games'),as_int=True); wins=number(row.get('wins'),as_int=True)
            valid_rate=games>0 and wins<=games
            quality='source-anomaly' if games and wins>games else ('estimated' if estimated else 'exact')
            ranked.append({'rank':rank,'player_id':row.get('player_id',row.get('id','')),'name':row.get('name',row.get('display_name',row.get('username',''))),'wins':wins,'games':games,'winrate':round(wins/games*100,2) if valid_rate else '','period_start':start,'period_end':end,'quality':quality,'source':source})
        filename=f"{month_id} ({datetime.strptime(start,'%Y-%m-%d').strftime('%d.%m.%y')}-{datetime.strptime(end,'%Y-%m-%d').strftime('%d.%m.%y')}).csv"
        with (output_dir/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=('rank','player_id','name','wins','games','winrate','period_start','period_end','quality','source')); writer.writeheader(); writer.writerows(ranked)
        leaderboards.append((month_id,ranked))
    # Finalized monthly leaderboard folders are the authoritative Win-Race result.
    for folder in sorted((tools_root/'Leaderboards Monthly Top100').glob('????-??')):
        month_id=folder.name
        if month_id >= current_id: continue
        path=folder/'assets.csv'
        if not path.exists(): path=folder/'leaderboard.csv'
        if not path.exists(): continue
        with path.open(encoding='utf-8-sig',newline='') as f: source_rows=list(csv.DictReader(f))[:50]
        snapshot_end=source_rows[0].get('source_snapshot','').split('/')[-1].removesuffix('.csv') if source_rows else f'{month_id}-01'
        next_month=(datetime.strptime(f'{month_id}-01','%Y-%m-%d')+timedelta(days=32)).replace(day=1).date()
        end=min(snapshot_end,(next_month-timedelta(days=1)).isoformat())
        rows=[{'player_id':r['player_id'],'name':r.get('display_name',''),'wins':r.get('monthly_wins',r.get('wins')),'games':r.get('monthly_games',r.get('games'))} for r in source_rows]
        save_leaderboard(month_id,f'{month_id}-01',end,rows,False,str(path.relative_to(tools_root)).replace('\\','/'))
        authoritative.add(month_id)
    # Exact 2026 monthly race exports: use the latest snapshot recorded for each month.
    for path in sorted((tools_root/'exports'/'monthly').glob('????-??_race.csv')):
        month_id=path.name[:7]
        if month_id >= current_id or month_id in authoritative: continue
        with path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        if not rows: continue
        end=max(row['date'] for row in rows); final=[row for row in rows if row['date']==end]
        final.sort(key=lambda row:(-number(row.get('wins'),as_int=True),-number(row.get('games'),as_int=True),row.get('id','')))
        save_leaderboard(month_id,f'{month_id}-01',end,final,False,str(path.relative_to(tools_root)).replace('\\','/'))
    # 2024/2025 archives contain cumulative snapshots. Use the observations nearest
    # each calendar boundary and rank monthly positive win deltas.
    for year in (2024,2025):
        path=tools_root/'exports'/'yearly'/f'{year}_race.csv'
        if not path.exists(): continue
        with path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        dates=sorted({row['date'] for row in rows}); by_date=defaultdict(dict)
        for row in rows: by_date[row['date']][row['id']]=row
        for month in range(1,13):
            month_id=f'{year}-{month:02d}'
            if month_id >= current_id: continue
            start=date(year,month,1); next_start=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
            before=min(dates,key=lambda d:abs((datetime.strptime(d,'%Y-%m-%d').date()-start).days),default=None)
            after=min(dates,key=lambda d:abs((datetime.strptime(d,'%Y-%m-%d').date()-next_start).days),default=None)
            if not before or not after or after <= before: continue
            deltas=[]
            for pid,end_row in by_date[after].items():
                start_row=by_date[before].get(pid)
                if not start_row: continue
                wins=number(end_row.get('wins'),as_int=True)-number(start_row.get('wins'),as_int=True)
                games=number(end_row.get('games'),as_int=True)-number(start_row.get('games'),as_int=True)
                # Counter resets/corrupt snapshots can otherwise create impossible
                # monthly records (for example more wins than games).
                if games>0 and 0<wins<=games: deltas.append({'id':pid,'name':end_row.get('username',''),'wins':wins,'games':games})
            deltas.sort(key=lambda item:(-item['wins'],-item['games'],item['id']))
            estimated=before!=start.isoformat() or after!=next_start.isoformat()
            save_leaderboard(month_id,before,after,deltas,estimated,str(path.relative_to(tools_root)).replace('\\','/'))
    for month_id,rows in leaderboards:
        for row in rows[:10]:
            results.append((row['player_id'],{'month':month_id,'monthLabel':datetime.strptime(month_id,'%Y-%m').strftime('%B %Y'),'rank':row['rank'],'wins':row['wins'],'periodStart':row['period_start'],'periodEnd':row['period_end'],'estimated':row['quality']!='exact'}))
    return results

def build_method_data(tools_root: Path, window_difficulty: dict, output_path: Path):
    """Build the public explanation examples and all-hour winner podiums."""
    latest={}
    snapshots=sorted((tools_root/'daily_snapshots').glob('*.csv'))
    if snapshots:
        with snapshots[-1].open(encoding='utf-8-sig',newline='') as f:
            latest={row.get('player_id',row.get('id','')):row for row in csv.DictReader(f)}
    all_hours=defaultdict(lambda:defaultdict(lambda:{'games':0,'wins':0}))
    exact_noon={}
    clean_times=[]
    for key,info in window_difficulty.items():
        try: clean_times.append(datetime.fromisoformat(info['windowStart']))
        except (KeyError,ValueError): pass
    for delta in sorted((tools_root/'hourly_deltas').glob('????-??-??/*.csv')):
        key=str(delta.relative_to(tools_root)).replace('\\','/')
        info=window_difficulty.get(key)
        if not info: continue
        with delta.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        if not rows: continue
        start=datetime.fromisoformat(info['windowStart']); hour=start.hour
        leaders=[]
        for row in rows:
            pid=(row.get('id') or row.get('player_id') or '').strip()
            games=number(row.get('games'),as_int=True); wins=number(row.get('wins'),as_int=True)
            if not pid: continue
            all_hours[hour][pid]['games']+=games; all_hours[hour][pid]['wins']+=wins
            leaders.append((wins,games,pid))
        if hour==12: exact_noon[start.date().isoformat()]={'start':start,'info':info,'leaders':leaders}
    def player(pid,wins,games):
        row=latest.get(pid,{})
        return {'id':pid,'name':row.get('display_name') or row.get('username') or pid[:8],'country':row.get('country',''),'wins':wins,'games':games,'winrate':round(wins/games*100,1) if games else 0}
    examples=[]
    dates=sorted(exact_noon)
    for day in dates:
        start=exact_noon[day]['start']
        if start.weekday()!=6 or start.hour!=12: continue
        monday=(start.date()+timedelta(days=1)).isoformat()
        if monday not in exact_noon: continue
        examples=[]
        for date_id,label in ((day,'Sunday'),(monday,'Monday')):
            item=exact_noon[date_id]
            top=sorted(item['leaders'],reverse=True)[:3]
            examples.append({'day':label,'date':date_id,'time':'12:00–13:00','lobbyBonus':round(item['info']['lobbyBonus'],1),'players':number(item['info'].get('players'),as_int=True),'games':number(item['info'].get('games'),as_int=True),'topPlayers':[player(pid,w,g) for w,g,pid in top]})
        # Prefer the newest complete Sunday/Monday pair.
    hour_top=[]
    for hour in range(24):
        top=sorted(((v['wins'],v['games'],pid) for pid,v in all_hours[hour].items()),reverse=True)[:3]
        hour_top.append({'hour':hour,'label':f'{hour:02d}:00–{(hour+1)%24:02d}:00','players':[player(pid,w,g) for w,g,pid in top]})
    coverage=0
    if clean_times:
        possible=max(1,int((max(clean_times)-min(clean_times)).total_seconds()/3600)+1)
        coverage=round(100*len(set(clean_times))/possible)
    doc={'generatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),'coveragePct':coverage,'examples':examples,'hourTop':hour_top}
    output_path.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

def build_method_data_v2(tools_root: Path, window_difficulty: dict, output_path: Path):
    """Build examples plus raw rolling windows for precise local-time grouping."""
    snapshots=sorted((tools_root/'daily_snapshots').glob('*.csv'))
    latest={}
    if snapshots:
        with snapshots[-1].open(encoding='utf-8-sig',newline='') as f:
            latest={row.get('player_id',row.get('id','')):row for row in csv.DictReader(f)}
    countries={}
    for asset in sorted((tools_root/'Leaderboards Monthly Top100').glob('????-??/assets.csv')):
        with asset.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                pid=row.get('player_id') or row.get('id'); country=row.get('country','')
                if pid and country: countries[pid]=country
    dated=[]; clean_times=[]
    for delta in sorted((tools_root/'hourly_deltas').glob('????-??-??/*.csv')):
        key=str(delta.relative_to(tools_root)).replace('\\','/'); info=window_difficulty.get(key)
        if not info: continue
        try: start=datetime.fromisoformat(info['windowStart'])
        except (KeyError,ValueError): continue
        dated.append((delta,info,start)); clean_times.append(start)
    newest=max(clean_times,default=datetime.now(timezone.utc)); cutoff=newest-timedelta(days=30)
    hour_windows=[]; exact_noon={}
    for delta,info,start in dated:
        with delta.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        leaders=[]; window_players=[]
        for row in rows:
            pid=(row.get('id') or row.get('player_id') or '').strip(); games=number(row.get('games'),as_int=True); wins=number(row.get('wins'),as_int=True)
            if not pid: continue
            leaders.append((wins,games,pid))
            if start>=cutoff and games>0: window_players.append({'id':pid,'games':games})
        if start>=cutoff:
            observed_games=number(info.get('games'),as_int=True) or sum(p['games'] for p in window_players)
            hour_windows.append({'timestamp':start.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),'games':observed_games,'lobbyFactor':round(1+number(info.get('lobbyBonus'))/100,4),'players':window_players})
        if start.hour==12: exact_noon[start.date().isoformat()]={'start':start,'info':info,'leaders':leaders}
    def player(pid,wins,games):
        row=latest.get(pid,{})
        return {'id':pid,'name':row.get('display_name') or row.get('username') or pid[:8],'country':row.get('country',''),'wins':wins,'games':games,'winrate':round(wins/games*100,1) if games else 0}
    examples=[]
    for day in sorted(exact_noon):
        start=exact_noon[day]['start']; monday=(start.date()+timedelta(days=1)).isoformat()
        if start.weekday()!=6 or monday not in exact_noon: continue
        examples=[]
        for date_id,label in ((day,'Sunday'),(monday,'Monday')):
            item=exact_noon[date_id]; top=sorted(item['leaders'],reverse=True)[:3]
            examples.append({'day':label,'date':date_id,'time':'12:00–13:00','lobbyBonus':round(item['info']['lobbyBonus'],1),'players':number(item['info'].get('players'),as_int=True),'games':number(item['info'].get('games'),as_int=True),'topPlayers':[player(pid,w,g) for w,g,pid in top]})
    current_players={pid:{'id':pid,'name':row.get('display_name') or row.get('username') or pid[:8],'country':countries.get(pid,row.get('country',''))} for pid,row in latest.items()}
    coverage=0
    if clean_times:
        possible=max(1,int((max(clean_times)-min(clean_times)).total_seconds()/3600)+1); coverage=round(100*len(set(clean_times))/possible)
    doc={'generatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),'coveragePct':coverage,'periodDays':30,'players':current_players,'hourWindows':hour_windows,'examples':examples}
    output_path.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

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
        monthly_wr=number(r.get('monthly_winrate',r.get('winrate')))
        players.append({'rank':int(r['rank']),'id':pid,'name':name,'aliases':aka,'country':r.get('country',''),'wins':number(r.get('monthly_wins',r.get('wins')),as_int=True),'games':number(r.get('monthly_games',r.get('games')),as_int=True),'deaths':number(r.get('monthly_deaths'),as_int=True),'winrate':monthly_wr,'monthlyWinrate':monthly_wr,'cleanWinrate':number(r.get('clean_winrate'),default=None),'expectedWinrate':number(r.get('expected_winrate'),default=None),'lobbyBonus':number(r.get('lobby_bonus'),default=None),'performanceScore':number(r.get('performance_score'),default=None),'deathrate':number(r.get('monthly_deathrate')),'ratedGames':number(r.get('skill_games'),as_int=True),'alltime':{'level':number(r.get('level'),default=None,as_int=True),'games':number(r.get('total_games'),default=None,as_int=True),'wins':number(r.get('total_wins'),default=None,as_int=True),'deaths':number(r.get('total_deaths'),default=None,as_int=True),'winstreak':None},'cosmetics':{key:r.get(key,'') for key in ('hat','suit','body','hand','color')}})
    label=datetime.strptime(month.name,'%Y-%m').strftime('%B %Y')
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),'month':month.name,'monthLabel':label,'current':month.name==date.today().strftime('%Y-%m'),'source':str(csv_path.relative_to(tools_root)).replace('\\','/'),'players':players}
    top_ids={p['id'] for p in players}
    window_difficulty={}
    window_path=tools_root/'output'/'window_lobby_difficulty.csv'
    if window_path.exists():
        with window_path.open(encoding='utf-8-sig',newline='') as f:
            window_difficulty={row['delta_file'].replace('\\','/'):{'lobbyBonus':number(row.get('lobby_bonus')),'confidence':row.get('confidence',''),'windowEffect':number(row.get('smoothed_window_effect')),'windowStart':row.get('window_start',''),'players':row.get('players',''),'games':row.get('games','')} for row in csv.DictReader(f)}
    build_method_data_v2(tools_root,window_difficulty,out/'method.json')
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
            delta_key=str(delta.relative_to(tools_root)).replace('\\','/')
            window_info=window_difficulty.get(delta_key,{})
            lobby_bonus=window_info.get('lobbyBonus',0)
            coverage_windows[timestamp]={'timestamp':timestamp,'difficulty':round(difficulties[hour],1),'lobbyBonus':round(lobby_bonus,2),'confidence':window_info.get('confidence','')}
            for row in delta_rows:
                pid=(row.get('id') or row.get('player_id') or '').strip()
                if pid not in top_ids: continue
                games=int(float(row.get('games') or 0)); wins=int(float(row.get('wins') or 0))
                hourly[pid][hour]['games']+=games; hourly[pid][hour]['wins']+=wins
                hourly[pid][hour]['dates'].add(day_dir.name)
                if games>0:
                    player_windows[pid].append({'timestamp':timestamp,'games':games,'wins':wins,'difficulty':round(difficulties[hour],1),'lobbyBonus':round(lobby_bonus,2)})
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
        pid=player['id']; rows=[]
        for hour in range(24):
            item=hourly[pid][hour]; games=item['games']; wins=item['wins']; days=len(coverage_by_hour[hour])
            rows.append({'hour':hour,'games':games,'wins':wins,'winrate':round(wins/games*100,2) if games else None,'gamesPerCoveredDay':round(games/days,3) if days else 0,'difficulty':round(difficulties[hour],1),'coveredDays':days})
        profile={**player,'month':month.name,'monthLabel':label,'sourceTimeZone':'Europe/Berlin','activityScaleMax':activity_scale_max,'performanceScaleMin':performance_scale_min,'performanceScaleMax':performance_scale_max,'monthlyWinrateValue':player['monthlyWinrate'],'cleanGames':sum(window['games'] for window in player_windows[pid]),'hourlyCoverageStart':min(coverage_dates) if coverage_dates else None,'hourlyCoverageEnd':max(coverage_dates) if coverage_dates else None,'coverageWindows':list(coverage_windows.values()),'hourlyWindows':player_windows[pid],'hourly':rows,'badges':[]}
        (monthly_dir/f'{pid}.json').write_text(json.dumps(profile,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    # Stable, reusable badge records. The active calendar month never awards a badge.
    badge_map=defaultdict(list)
    current_id=date.today().strftime('%Y-%m')
    for pid,record in historical_badge_rows(tools_root,current_id,out/'historical-leaderboards'): badge_map[pid].append(record)
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
