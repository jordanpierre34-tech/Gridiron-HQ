"""2026 football analytics backend. pip install flask requests pandas pyarrow"""
import os, io, time, datetime, threading
from collections import defaultdict
import requests
from flask import Flask, jsonify, send_from_directory

app=Flask(__name__,static_folder='.')
SEASON=2026
CACHE={'value':None,'at':0}
LOCK=threading.Lock()
NFL=['Arizona Cardinals','Atlanta Falcons','Baltimore Ravens','Buffalo Bills','Carolina Panthers','Chicago Bears','Cincinnati Bengals','Cleveland Browns','Dallas Cowboys','Denver Broncos','Detroit Lions','Green Bay Packers','Houston Texans','Indianapolis Colts','Jacksonville Jaguars','Kansas City Chiefs','Las Vegas Raiders','Los Angeles Chargers','Los Angeles Rams','Miami Dolphins','Minnesota Vikings','New England Patriots','New Orleans Saints','New York Giants','New York Jets','Philadelphia Eagles','Pittsburgh Steelers','San Francisco 49ers','Seattle Seahawks','Tampa Bay Buccaneers','Tennessee Titans','Washington Commanders']
ABBR={'ARI':'Arizona Cardinals','ATL':'Atlanta Falcons','BAL':'Baltimore Ravens','BUF':'Buffalo Bills','CAR':'Carolina Panthers','CHI':'Chicago Bears','CIN':'Cincinnati Bengals','CLE':'Cleveland Browns','DAL':'Dallas Cowboys','DEN':'Denver Broncos','DET':'Detroit Lions','GB':'Green Bay Packers','HOU':'Houston Texans','IND':'Indianapolis Colts','JAX':'Jacksonville Jaguars','KC':'Kansas City Chiefs','LV':'Las Vegas Raiders','LAC':'Los Angeles Chargers','LA':'Los Angeles Rams','LAR':'Los Angeles Rams','MIA':'Miami Dolphins','MIN':'Minnesota Vikings','NE':'New England Patriots','NO':'New Orleans Saints','NYG':'New York Giants','NYJ':'New York Jets','PHI':'Philadelphia Eagles','PIT':'Pittsburgh Steelers','SF':'San Francisco 49ers','SEA':'Seattle Seahawks','TB':'Tampa Bay Buccaneers','TEN':'Tennessee Titans','WAS':'Washington Commanders'}
def base(name,league,conference='',abbr=''):
 return dict(name=name,league=league,conference=conference,abbr=abbr,games=None,off_epa=None,def_epa=None,off_success=None,def_success=None,off_ypp=None,def_ypp=None,point_diff=None)
def value(obj,*keys):
 for key in keys:
  if isinstance(obj,dict) and obj.get(key) is not None:return obj[key]
 return None
def cfbd(path,params={}):
 key=os.getenv('CFBD_API_KEY')
 if not key:raise RuntimeError('CFBD_API_KEY not set')
 r=requests.get('https://api.collegefootballdata.com'+path,params=params,headers={'Authorization':'Bearer '+key},timeout=35);r.raise_for_status();return r.json()
def get_nfl(data,errors):
 try:
  import pandas as pd
  url=f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{SEASON}.parquet'
  r=requests.get(url,timeout=90);r.raise_for_status();df=pd.read_parquet(io.BytesIO(r.content));df=df[(df['season']==SEASON)&(df['season_type']=='REG')]
  df=df[df['play_type'].isin(['pass','run']) & df['posteam'].notna()].copy()
  df['total_yards']=df['yards_gained'];df['total_yards']=pd.to_numeric(df['total_yards'],errors='coerce')
  for side,col in [('off','posteam'),('def','defteam')]:
   for abbr,g in df.groupby(col):
    name=ABBR.get(abbr)
    if not name:continue
    row=next(x for x in data['teams'] if x['league']=='NFL' and x['name']==name)
    row[side+'_epa']=safe_mean(g['epa']);row[side+'_success']=safe_mean(g['success']);row[side+'_ypp']=safe_mean(g['total_yards'])
  games=df[['game_id','posteam']].drop_duplicates().groupby('posteam').size().to_dict()
  for abbr,n in games.items():
   if abbr in ABBR:next(x for x in data['teams'] if x['name']==ABBR[abbr])['games']=int(n)
  scores=df[['game_id','home_team','away_team','home_score','away_score']].drop_duplicates('game_id')
  for _,g in scores.iterrows():
   for abbr,sign in [(g.home_team,1),(g.away_team,-1)]:
    if abbr in ABBR and pd.notna(g.home_score) and pd.notna(g.away_score):
     row=next(x for x in data['teams'] if x['name']==ABBR[abbr]);row['point_diff']=(row['point_diff'] or 0)+int(sign*(g.home_score-g.away_score))
  data['meta']['nfl_source']=url
 except Exception as e:errors.append('NFL play-by-play: '+str(e))
 try:
  import pandas as pd
  url=f'https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats_{SEASON}.parquet'
  r=requests.get(url,timeout=60);r.raise_for_status();p=pd.read_parquet(io.BytesIO(r.content));p=p[p['season_type']=='REG']
  if 'week' in p.columns:p=p[p['week'].notna()]
  for (pid,team),g in p.groupby(['player_id','recent_team'],dropna=True):
   if team not in ABBR:continue
   first=g.iloc[0];s=lambda c:float(pd.to_numeric(g[c],errors='coerce').sum()) if c in g else None
   data['players'].append(dict(league='NFL',name=str(first.get('player_display_name') or first.get('player_name') or pid),team=ABBR[team],position=str(first.get('position','')),games=int(g['week'].nunique()) if 'week' in g else None,pass_yards=s('passing_yards'),rush_yards=s('rushing_yards'),rec_yards=s('receiving_yards'),receptions=s('receptions'),touchdowns=sum(s(c) or 0 for c in ['passing_tds','rushing_tds','receiving_tds'])))
  data['meta']['nfl_player_source']=url
 except Exception as e:errors.append('NFL player statistics: '+str(e))
def safe_mean(s):
 import pandas as pd
 n=pd.to_numeric(s,errors='coerce').mean();return float(n) if pd.notna(n) else None
def get_fbs(data,errors):
 try:
  teams=cfbd('/teams/fbs',{'year':SEASON})
  for t in teams:
   name=value(t,'school','name');conf=value(t,'conference') or ''
   if name:data['teams'].append(base(name,'FBS',conf,value(t,'abbreviation') or ''))
  data['fbs_teams']=[t['name'] for t in data['teams'] if t['league']=='FBS']
 except Exception as e:errors.append('FBS directory: '+str(e));return
 index={t['name']:t for t in data['teams'] if t['league']=='FBS'}
 try:
  for a in cfbd('/stats/season/advanced',{'year':SEASON,'excludeGarbageTime':'true'}):
   row=index.get(value(a,'team'))
   if not row:continue
   off=a.get('offense') or {};de=a.get('defense') or {}
   row['off_success']=value(off,'successRate');row['def_success']=value(de,'successRate')
   row['off_epa']=value(off,'epaPerPlay');row['def_epa']=value(de,'epaPerPlay')
   # CFBD advanced stats may provide PPA rather than EPA; never silently relabel PPA as EPA.
 except Exception as e:errors.append('FBS advanced statistics: '+str(e))
 try:
  games=cfbd('/games',{'year':SEASON,'seasonType':'regular','division':'fbs'})
  for g in games:
   hs=value(g,'homePoints');a=value(g,'awayPoints')
   if hs is None or a is None:continue
   for team,delta in [(g.get('homeTeam'),hs-a),(g.get('awayTeam'),a-hs)]:
    if team in index:
     row=index[team];row['games']=(row['games'] or 0)+1;row['point_diff']=(row['point_diff'] or 0)+delta
 except Exception as e:errors.append('FBS scores: '+str(e))
 try:
  stats=cfbd('/stats/season',{'year':SEASON})
  by=defaultdict(dict)
  for x in stats:by[x.get('team')][x.get('statName')]=x.get('statValue')
  for team,stats in by.items():
   row=index.get(team)
   if not row:continue
   # Basic season stats have different play denominators; only populate YPP when both verified.
   try:
    yards=float(stats['totalYards']);plays=float(stats['totalPlays']);row['off_ypp']=yards/plays if plays else None
   except (ValueError,KeyError,TypeError):pass
 except Exception as e:errors.append('FBS team stats: '+str(e))
 try:
  stats=cfbd('/stats/player/season',{'year':SEASON})
  grouped=defaultdict(dict)
  for x in stats:
   key=(x.get('playerId') or x.get('player'),x.get('team'),x.get('category'))
   grouped[key][x.get('statType')]=x.get('stat')
  players=defaultdict(lambda:dict(league='FBS',name='',team='',position='',games=None,pass_yards=None,rush_yards=None,rec_yards=None,receptions=None,touchdowns=None))
  for (pid,team,category),v in grouped.items():
   if team not in index:continue
   p=players[(pid,team)];p['name']=str(pid);p['team']=team
   def n(k):
    try:return float(v[k])
    except (ValueError,TypeError,KeyError):return None
   if category=='passing':p['pass_yards']=n('YDS')
   if category=='rushing':p['rush_yards']=n('YDS')
   if category=='receiving':p['rec_yards']=n('YDS');p['receptions']=n('REC')
  data['players'].extend(players.values())
 except Exception as e:errors.append('FBS player statistics: '+str(e))
 data['meta']['cfbd_source']='https://api.collegefootballdata.com'
def build():
 data={'teams':[base(t,'NFL') for t in NFL],'players':[],'fbs_teams':[],'meta':{'season':SEASON,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'errors':[]}}
 get_nfl(data,data['meta']['errors']);get_fbs(data,data['meta']['errors']);return data
@app.route('/')
def home():return send_from_directory('.','index.html')
@app.route('/api/data')
def api():
 from flask import request
 with LOCK:
  if CACHE['value'] is None or time.time()-CACHE['at']>21600 or request.args.get('refresh')=='1':
   CACHE['value']=build();CACHE['at']=time.time()
  return jsonify(CACHE['value'])
if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=False)
