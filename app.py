import csv, io, json, os, uuid, copy
from datetime import datetime
from flask import Flask, jsonify, request, render_template, Response

BASE=os.path.dirname(os.path.abspath(__file__))
DATA=os.path.join(BASE,'data'); os.makedirs(DATA,exist_ok=True)
STATE_FILE=os.path.join(DATA,'state.json')
app=Flask(__name__)

def uid(prefix): return f"{prefix}_{uuid.uuid4().hex[:10]}"
def now(): return datetime.now().isoformat(timespec='seconds')

def new_project(name='אולם חדש'):
    tables=[]
    for r in range(5):
        for c in range(6):
            tables.append({'id':uid('t'),'name':f'שולחן {r*6+c+1}','x':8+c*15.5,'y':14+r*16,'capacity':4,
                           'rank':round(1+r*1.0+abs(c-2.5)*.35,2),'custom_rank':False,'locked':False,'kind':'table','shape':'round'})
    return {'id':uid('p'),'name':name,'created':now(),'modified':now(),
            'hall':{'name':'האולם','stage_label':'חזית / במה','width':100,'height':100,'seating_type':'round_tables'},
            'tables':tables,'hall_objects':[],'settings':{'seat_preference':'front_center','front_weight':1.0,'center_weight':0.35,'show_quality':False,'assignment_zoom':1.0,'grid_cols':26,'grid_rows':16},'groups':[], 'people':[], 'rules':[], 'snapshots':[]}

def default_state():
    p=new_project('השיבוץ הראשון')
    return {'version':2,'active_project':p['id'],'projects':[p]}

def load():
    if not os.path.exists(STATE_FILE):
        s=default_state(); save(s); return s
    try:
        with open(STATE_FILE,encoding='utf-8') as f: return json.load(f)
    except Exception:
        s=default_state(); save(s); return s

def save(s):
    with open(STATE_FILE,'w',encoding='utf-8') as f: json.dump(s,f,ensure_ascii=False,indent=2)
STATE=load()

def project():
    pid=STATE.get('active_project')
    return next((p for p in STATE['projects'] if p['id']==pid),None)
def touch(p): p['modified']=now(); save(STATE)
def person_by_id(p,pid): return next((x for x in p['people'] if x['id']==pid),None)
def table_by_id(p,tid): return next((x for x in p['tables'] if x['id']==tid),None)
def group_by_id(p,gid): return next((x for x in p['groups'] if x['id']==gid),None)
def occupants(p,tid): return [x for x in p['people'] if x.get('table_id')==tid]
def free_seat(p,t):
    used={x.get('seat') for x in occupants(p,t['id'])}
    return next((i for i in range(t['capacity']) if i not in used),None)
def renumber_groups(p):
    p['groups'].sort(key=lambda g:g.get('priority',9999))
    for i,g in enumerate(p['groups'],1): g['priority']=i

def violations(p):
    out=[]; by={x['id']:x for x in p['people']}
    for rule in p['rules']:
        ids=[i for i in rule.get('people',[]) if i in by]
        if not ids: continue
        typ=rule.get('type'); bad=False; msg=''
        if typ=='together' and len(ids)>1:
            seats=[by[i].get('table_id') for i in ids]
            bad=any(not x for x in seats) or len(set(seats))>1
            msg='האנשים בכלל אינם יושבים יחד באותו שולחן'
        elif typ=='separate' and len(ids)>1:
            seats=[by[i].get('table_id') for i in ids if by[i].get('table_id')]
            bad=len(seats)!=len(set(seats)); msg='אנשים שאמורים להיות בנפרד יושבים באותו שולחן'
        elif typ in ('at_table','not_table') and len(ids)==1:
            cur=by[ids[0]].get('table_id'); target=rule.get('table_id')
            bad=(cur!=target) if typ=='at_table' else (cur==target); msg='השיבוץ אינו עומד בדרישת השולחן'
        if bad: out.append({'rule_id':rule['id'],'level':rule.get('level','soft'),'message':msg})
    return out

def effective_rank(p,t):
    if t.get('custom_rank'): return float(t.get('rank',10))
    s=p.get('settings',{}); mode=s.get('seat_preference','front_center')
    fw=float(s.get('front_weight',1.0)); cw=float(s.get('center_weight',0.35))
    front=max(0.0,min(100.0,float(t.get('y',50))))/10.0
    center=abs(max(0.0,min(100.0,float(t.get('x',50))))-50.0)/5.0
    if mode=='front_only': return front
    if mode=='center_only': return center
    if mode=='manual': return float(t.get('rank',10))
    return front*fw + center*cw

def score_candidate(p,person,t,group_priority):
    score=effective_rank(p,t)*10 + group_priority*2
    pzone=str(person.get('preferred_zone') or '').strip()
    if pzone: score += (-45 if str(t.get('zone') or '').strip()==pzone else 18)
    ptags=set(person.get('preferred_tags') or [])
    if ptags:
        matches=len(ptags.intersection(set(t.get('tags') or [])))
        score-=matches*18
    pref=person.get('seat_preference','project')
    if pref=='front': score += max(0.0,min(100.0,float(t.get('y',50))))*.25
    elif pref=='center': score += abs(float(t.get('x',50))-50)*.18
    same=sum(1 for x in occupants(p,t['id']) if x.get('group_id')==person.get('group_id'))
    other=len(occupants(p,t['id']))-same
    score-=same*9; score+=other*2
    for r in p['rules']:
        if person['id'] not in r.get('people',[]): continue
        hard=r.get('level')=='hard'; penalty=180; typ=r.get('type'); violates=False
        if typ=='at_table':
            violates=t['id']!=r.get('table_id')
        elif typ=='not_table':
            violates=t['id']==r.get('table_id')
        elif typ=='together':
            mates=[person_by_id(p,i) for i in r.get('people',[]) if i!=person['id']]
            seated=[m for m in mates if m and m.get('table_id')]
            violates=bool(seated and any(m['table_id']!=t['id'] for m in seated))
        elif typ=='separate':
            mates=set(r.get('people',[]))-{person['id']}
            violates=any(o['id'] in mates for o in occupants(p,t['id']))
        if violates:
            if hard:return None
            score+=penalty
    return score

@app.get('/')
def index(): return render_template('index.html')
@app.get('/api/state')
def state(): return jsonify({'state':STATE,'project':project(),'violations':violations(project()) if project() else []})

@app.post('/api/projects')
def add_project():
    d=request.get_json(force=True); p=new_project((d.get('name') or 'פרויקט חדש').strip())
    STATE['projects'].append(p); STATE['active_project']=p['id']; save(STATE); return state()
@app.post('/api/projects/<pid>/activate')
def activate(pid):
    if not any(p['id']==pid for p in STATE['projects']): return jsonify(error='project not found'),404
    STATE['active_project']=pid; save(STATE); return state()
@app.delete('/api/projects/<pid>')
def del_project(pid):
    if len(STATE['projects'])<=1: return jsonify(error='לא ניתן למחוק את הפרויקט האחרון'),400
    STATE['projects']=[p for p in STATE['projects'] if p['id']!=pid]
    if STATE['active_project']==pid: STATE['active_project']=STATE['projects'][0]['id']
    save(STATE); return state()
@app.post('/api/project/name')
def project_name():
    p=project(); p['name']=(request.get_json(force=True).get('name') or p['name']).strip(); touch(p); return state()

@app.post('/api/project/settings')
def project_settings():
    p=project(); d=request.get_json(force=True); s=p.setdefault('settings',{})
    mode=d.get('seat_preference',s.get('seat_preference','front_center'))
    if mode not in ('front_center','front_only','center_only','manual'):return jsonify(error='העדפת מקום לא תקינה'),400
    s['seat_preference']=mode
    for k,default in (('front_weight',1.0),('center_weight',0.35)):
        if k in d:s[k]=max(0.0,min(10.0,float(d[k])))
        else:s.setdefault(k,default)
    if 'show_quality' in d:s['show_quality']=bool(d['show_quality'])
    if 'assignment_zoom' in d:s['assignment_zoom']=max(.6,min(2.0,float(d['assignment_zoom'])))
    old_cols=max(5,int(s.get('grid_cols',26))); old_rows=max(5,int(s.get('grid_rows',16)))
    new_cols=max(5,min(120,int(d.get('grid_cols',old_cols)))); new_rows=max(5,min(80,int(d.get('grid_rows',old_rows))))
    max_x=max([int(x.get('gx',0))+int(x.get('gw',1)) for x in p.get('tables',[])+p.get('hall_objects',[]) if x.get('gx') is not None] or [0])
    max_y=max([int(x.get('gy',0))+int(x.get('gh',1)) for x in p.get('tables',[])+p.get('hall_objects',[]) if x.get('gy') is not None] or [0])
    if new_cols<max_x or new_rows<max_y:return jsonify(error=f'לא ניתן להקטין ל-{new_cols}×{new_rows}: יש פריטים מחוץ לגודל החדש'),400
    s['grid_cols']=new_cols; s['grid_rows']=new_rows
    touch(p);return state()

@app.get('/api/validate')
def validate_project():
    p=project(); issues=[]; cap=sum(int(t.get('capacity',1)) for t in p['tables'] if not t.get('disabled'))
    if cap < len(p['people']): issues.append({'level':'hard','message':f'חסרים {len(p["people"])-cap} מקומות ישיבה'})
    ids={t['id'] for t in p['tables']}
    for r in p['rules']:
        if r.get('table_id') and r.get('table_id') not in ids:issues.append({'level':'hard','message':'כלל מפנה למקום שכבר אינו קיים'})
    for t in p['tables']:
        if not (0<=float(t.get('x',0))<=100 and 0<=float(t.get('y',0))<=100):issues.append({'level':'soft','message':f'{t.get("name","מקום")} נמצא מחוץ לגבולות האולם'})
    seen={}
    for t in p['tables']:
        key=(round(float(t.get('x',0)),1),round(float(t.get('y',0)),1))
        if key in seen:issues.append({'level':'soft','message':f'ייתכן חפיפה בין {seen[key]} לבין {t.get("name","מקום")}'})
        seen[key]=t.get('name','מקום')
    return jsonify({'issues':issues,'capacity':cap,'people':len(p['people']),'unassigned':sum(1 for x in p['people'] if not x.get('table_id'))})

@app.get('/api/explain/<pid>')
def explain_assignment(pid):
    p=project(); x=person_by_id(p,pid)
    if not x:return jsonify(error='person not found'),404
    t=table_by_id(p,x.get('table_id')) if x.get('table_id') else None
    if not t:return jsonify({'title':x['name'],'lines':['האדם עדיין אינו משובץ']})
    lines=[f'מקום: {t.get("name","")}',f'דירוג מיקום: {effective_rank(p,t):.2f}']
    if x.get('preferred_zone'):lines.append(('✓ ' if t.get('zone')==x.get('preferred_zone') else '○ ')+f'אזור מועדף: {x.get("preferred_zone")}')
    tags=set(x.get('preferred_tags') or []).intersection(set(t.get('tags') or []))
    if tags:lines.append('✓ תגיות מתאימות: '+', '.join(sorted(tags)))
    g=group_by_id(p,x.get('group_id')) if x.get('group_id') else None
    if g:lines.append(f'קדימות קבוצה: {g.get("priority",999)}')
    return jsonify({'title':x['name'],'lines':lines,'rank':effective_rank(p,t)})

@app.post('/api/hall')
def hall():
    p=project(); d=request.get_json(force=True)
    for k in ('name','stage_label','seating_type'):
        if k in d: p['hall'][k]=str(d[k]).strip()
    touch(p); return state()

@app.post('/api/layout/draw')
def draw_layout_item():
    p=project();d=request.get_json(force=True);kind=d.get('kind')
    # Geometry uses the project's configurable logical grid.
    cols=max(5,int(p.get('settings',{}).get('grid_cols',26))); rows=max(5,int(p.get('settings',{}).get('grid_rows',16)))
    gx=max(0,min(cols-1,int(d.get('gx',0)))); gy=max(0,min(rows-1,int(d.get('gy',0))))
    gw=max(1,min(cols-gx,int(d.get('gw',1)))); gh=max(1,min(rows-gy,int(d.get('gh',1))))
    x=(gx+gw/2)/cols*100; y=(gy+gh/2)/rows*100; w=gw/cols*100; h=gh/rows*100
    created=[]
    def seat_cell(cx,cy,name,bench_id=None,index=None):
        px=(cx+.5)/cols*100; py=(cy+.5)/rows*100
        t={'id':uid('t'),'name':name,'x':px,'y':py,'capacity':1,'rank':max(1,round(py/10,1)),
           'custom_rank':False,'locked':False,'kind':'seat','shape':'chair','rotation':0,
           'w':100/cols,'h':100/rows,'gx':cx,'gy':cy,'gw':1,'gh':1,'zone':'','tags':[],'disabled':False}
        if bench_id:t['bench_id']=bench_id;t['bench_index']=index
        p['tables'].append(t);created.append(t['id'])
    if kind in ('round','square'):
        t={'id':uid('t'),'name':f"שולחן {len([q for q in p['tables'] if q.get('kind')!='seat'])+1}",
           'x':x,'y':y,'capacity':max(1,min(30,int(d.get('capacity',4)))),'rank':max(1,round(y/10,1)),
           'custom_rank':False,'locked':False,'kind':'table','shape':'round' if kind=='round' else 'square',
           'rotation':0,'w':w,'h':h,'gx':gx,'gy':gy,'gw':gw,'gh':gh,'zone':'','tags':[],'disabled':False}
        p['tables'].append(t);created.append(t['id'])
    elif kind=='seat':
        # Like the room editor's swept corridor: every covered grid square becomes one cell.
        for rr in range(gh):
            for cc in range(gw):
                seat_cell(gx+cc,gy+rr,f'כיסא {len([q for q in p["tables"] if q.get("kind")=="seat"])+1}')
    elif kind=='bench':
        horizontal=gw>=gh; count=gw if horizontal else gh; bid=uid('bench')
        fixed_y=gy+(gh-1)//2; fixed_x=gx+(gw-1)//2
        for i in range(count):
            seat_cell(gx+i if horizontal else fixed_x,fixed_y if horizontal else gy+i,f'ספסל {bid[-4:]} · מקום {i+1}',bid,i+1)
    elif kind in ('stage','aisle','zone'):
        names={'stage':'במה','aisle':'מעבר','zone':'אזור'}
        o={'id':uid('o'),'kind':kind,'name':names[kind],'x':x,'y':y,'w':w,'h':h,'rotation':0,
           'gx':gx,'gy':gy,'gw':gw,'gh':gh}
        p.setdefault('hall_objects',[]).append(o);created.append(o['id'])
    else:return jsonify(error='סוג שרטוט לא מוכר'),400
    touch(p);return jsonify(created=created,**state().get_json())

@app.post('/api/tables')
def add_table():
    p=project(); d=request.get_json(force=True)
    t={'id':uid('t'),'name':(d.get('name') or f"שולחן {len(p['tables'])+1}").strip(),
       'x':float(d.get('x',50)),'y':float(d.get('y',50)),'capacity':max(1,int(d.get('capacity',4))),
       'rank':float(d.get('rank',10)),'custom_rank':bool(d.get('custom_rank',False)),'locked':False,'kind':d.get('kind','table'),'shape':d.get('shape','round'),'rotation':float(d.get('rotation',0)),'w':float(d.get('w',0)),'h':float(d.get('h',0)),'zone':str(d.get('zone','')).strip(),'tags':d.get('tags',[]) if isinstance(d.get('tags',[]),list) else [],'disabled':bool(d.get('disabled',False))}
    p['tables'].append(t); touch(p); return state()
@app.patch('/api/tables/<tid>')
def edit_table(tid):
    p=project(); t=table_by_id(p,tid)
    if not t:return jsonify(error='table not found'),404
    d=request.get_json(force=True)
    if 'name' in d:t['name']=str(d['name']).strip()
    for k in ('kind','shape','zone'):
        if k in d:t[k]=str(d[k])
    for k in ('x','y','rank','rotation','w','h'):
        if k in d:t[k]=float(d[k])
    for k in ('gx','gy','gw','gh'):
        if k in d:t[k]=int(d[k])
    if 'capacity' in d:
        cap=max(1,int(d['capacity'])); occ=occupants(p,tid)
        if len(occ)>cap:return jsonify(error='יש יותר משובצים מהקיבולת החדשה'),400
        t['capacity']=cap
    if 'locked' in d:t['locked']=bool(d['locked'])
    if 'custom_rank' in d:t['custom_rank']=bool(d['custom_rank'])
    if 'tags' in d:t['tags']=d['tags'] if isinstance(d['tags'],list) else []
    if 'disabled' in d:t['disabled']=bool(d['disabled'])
    touch(p); return state()
@app.delete('/api/tables/<tid>')
def delete_table(tid):
    p=project()
    for x in occupants(p,tid):
        if x.get('locked'): return jsonify(error='יש בשולחן אדם נעול. בטל נעילה לפני מחיקה'),400
        x['table_id']=None;x['seat']=None
    p['tables']=[t for t in p['tables'] if t['id']!=tid]; p['rules']=[r for r in p['rules'] if r.get('table_id')!=tid]
    touch(p); return state()

@app.post('/api/layout/clear')
def clear_layout():
    p=project()
    if any(x.get('locked') and x.get('table_id') for x in p['people']):
        return jsonify(error='יש אנשים נעולים במקומם. בטל נעילות לפני ניקוי האולם'),400
    for x in p['people']:
        x['table_id']=None; x['seat']=None
    p['tables']=[]; p['rules']=[r for r in p['rules'] if not r.get('table_id')]
    p['hall_objects']=[]
    touch(p); return state()

@app.post('/api/layout/generate')
def generate_layout():
    p=project(); d=request.get_json(force=True)
    gcols=max(5,int(p.get('settings',{}).get('grid_cols',26))); grows=max(5,int(p.get('settings',{}).get('grid_rows',16)))
    mode=d.get('mode','rows'); rows=max(1,min(30,int(d.get('rows',5)))); cols=max(1,min(30,int(d.get('cols',8))))
    cap=max(1,min(30,int(d.get('capacity',4))))
    if any(x.get('locked') and x.get('table_id') for x in p['people']):
        return jsonify(error='יש אנשים נעולים במקומם. בטל נעילות לפני החלפת המבנה'),400
    for x in p['people']: x['table_id']=None; x['seat']=None
    p['tables']=[]; p['rules']=[r for r in p['rules'] if not r.get('table_id')]
    if mode=='rows':
        p['hall']['seating_type']='rows'
        for r in range(rows):
            for col in range(cols):
                gx=round((gcols-1)*(col/(max(1,cols-1)))); gy=round((grows-1)*(r/(max(1,rows-1))))
                p['tables'].append({'id':uid('t'),'name':f'שורה {r+1} · כיסא {col+1}','x':(gx+.5)/gcols*100,'y':(gy+.5)/grows*100,'capacity':1,'rank':round(1+r+abs(col-(cols-1)/2)*.08,2),'custom_rank':False,'locked':False,'kind':'seat','shape':'chair','rotation':0,'w':100/gcols,'h':100/grows,'gx':gx,'gy':gy,'gw':1,'gh':1,'zone':'','tags':[],'disabled':False})
    else:
        p['hall']['seating_type']='square_tables' if mode=='square' else 'round_tables'
        shape='square' if mode=='square' else 'round'
        for r in range(rows):
            for col in range(cols):
                gx=round((gcols-1)*(col/(max(1,cols-1)))); gy=round((grows-1)*(r/(max(1,rows-1))))
                p['tables'].append({'id':uid('t'),'name':f'שולחן {r*cols+col+1}','x':(gx+.5)/gcols*100,'y':(gy+.5)/grows*100,'capacity':cap,'rank':round(1+r+abs(col-(cols-1)/2)*.3,2),'custom_rank':False,'locked':False,'kind':'table','shape':shape,'rotation':0,'w':100/gcols,'h':100/grows,'gx':gx,'gy':gy,'gw':1,'gh':1,'zone':'','tags':[],'disabled':False})
    touch(p); return state()

@app.post('/api/tables/bulk')
def bulk_tables():
    p=project(); d=request.get_json(force=True); ids=set(d.get('ids',[])); action=d.get('action')
    cols=max(5,int(p.get('settings',{}).get('grid_cols',26))); rows=max(5,int(p.get('settings',{}).get('grid_rows',16)))
    items=[t for t in p['tables'] if t['id'] in ids]
    if not items:return jsonify(error='לא נבחרו פריטים'),400
    if action=='delete':
        locked=[x for x in p['people'] if x.get('table_id') in ids and x.get('locked')]
        if locked:return jsonify(error='יש אנשים נעולים בפריטים שנבחרו'),400
        for x in p['people']:
            if x.get('table_id') in ids:x['table_id']=None;x['seat']=None
        p['tables']=[t for t in p['tables'] if t['id'] not in ids]
        p['rules']=[r for r in p['rules'] if r.get('table_id') not in ids]
    elif action=='move':
        dx=float(d.get('dx',0));dy=float(d.get('dy',0));gdx=int(d.get('grid_dx',0));gdy=int(d.get('grid_dy',0))
        for t in items:
            if t.get('gx') is not None:
                gw=max(1,int(t.get('gw',1)));gh=max(1,int(t.get('gh',1)))
                t['gx']=max(0,min(cols-gw,int(t.get('gx',0))+gdx));t['gy']=max(0,min(rows-gh,int(t.get('gy',0))+gdy))
                t['x']=(t['gx']+gw/2)/cols*100;t['y']=(t['gy']+gh/2)/rows*100
            else:
                t['x']=max(1,min(99,float(t.get('x',50))+dx));t['y']=max(1,min(99,float(t.get('y',50))+dy))
    elif action=='align':
        mode=d.get('mode')
        gridded=[t for t in items if t.get('gx') is not None]
        if len(gridded)==len(items):
            if mode in ('left','right','hcenter'):
                vals=[int(t.get('gx',0)) for t in items]
                val=min(vals) if mode=='left' else max(vals) if mode=='right' else round(sum(vals)/len(vals))
                for t in items:
                    gw=max(1,int(t.get('gw',1)));t['gx']=max(0,min(cols-gw,val));t['x']=(t['gx']+gw/2)/cols*100
            elif mode in ('top','bottom','vcenter'):
                vals=[int(t.get('gy',0)) for t in items]
                val=min(vals) if mode=='top' else max(vals) if mode=='bottom' else round(sum(vals)/len(vals))
                for t in items:
                    gh=max(1,int(t.get('gh',1)));t['gy']=max(0,min(rows-gh,val));t['y']=(t['gy']+gh/2)/rows*100
        else:
            if mode in ('left','right','hcenter'):
                val=min(t['x'] for t in items) if mode=='left' else max(t['x'] for t in items) if mode=='right' else sum(t['x'] for t in items)/len(items)
                for t in items:t['x']=val
            elif mode in ('top','bottom','vcenter'):
                val=min(t['y'] for t in items) if mode=='top' else max(t['y'] for t in items) if mode=='bottom' else sum(t['y'] for t in items)/len(items)
                for t in items:t['y']=val
    elif action=='distribute':
        axis=d.get('axis','x'); gridded=[t for t in items if t.get('gx') is not None]
        if len(items)>2 and len(gridded)==len(items):
            key='gx' if axis=='x' else 'gy'; ordered=sorted(items,key=lambda t:int(t.get(key,0)))
            startv=int(ordered[0].get(key,0));endv=int(ordered[-1].get(key,0));step=(endv-startv)/(len(ordered)-1)
            for i,t in enumerate(ordered):
                if axis=='x':
                    gw=max(1,int(t.get('gw',1)));t['gx']=max(0,min(cols-gw,round(startv+i*step)));t['x']=(t['gx']+gw/2)/cols*100
                else:
                    gh=max(1,int(t.get('gh',1)));t['gy']=max(0,min(rows-gh,round(startv+i*step)));t['y']=(t['gy']+gh/2)/rows*100
        elif len(items)>2:
            key='x' if axis=='x' else 'y'; ordered=sorted(items,key=lambda t:t[key]);startv=ordered[0][key];endv=ordered[-1][key];step=(endv-startv)/(len(ordered)-1)
            for i,t in enumerate(ordered):t[key]=startv+i*step
    elif action=='duplicate':
        new=[]
        for t in items:
            n=copy.deepcopy(t);n['id']=uid('t');n['name']=str(t.get('name','פריט'))+' עותק';n['x']=min(98,t['x']+3);n['y']=min(97,t['y']+3)
            if n.get('gx') is not None:
                n['gx']=min(cols-int(n.get('gw',1)),int(n['gx'])+2);n['gy']=min(rows-int(n.get('gh',1)),int(n['gy'])+2)
                n['x']=(n['gx']+int(n.get('gw',1))/2)/cols*100;n['y']=(n['gy']+int(n.get('gh',1))/2)/rows*100
            if n.get('bench_id'):n['bench_id']=uid('bench')
            new.append(n)
        p['tables'].extend(new)
    elif action=='rotate':
        deg=float(d.get('degrees',90))
        for t in items:t['rotation']=(float(t.get('rotation',0))+deg)%360
    else:return jsonify(error='פעולה לא מוכרת'),400
    touch(p);return state()

@app.post('/api/layout/restore')
def restore_layout():
    p=project(); d=request.get_json(force=True)
    tables=d.get('tables')
    if not isinstance(tables,list):return jsonify(error='מצב שחזור לא תקין'),400
    valid={t.get('id') for t in tables}
    for x in p['people']:
        if x.get('table_id') not in valid:x['table_id']=None;x['seat']=None
    p['tables']=copy.deepcopy(tables)
    if 'hall_objects' in d:p['hall_objects']=copy.deepcopy(d.get('hall_objects') or [])
    assignments=d.get('assignments')
    if isinstance(assignments,list):
        amap={a.get('id'):a for a in assignments}
        valid={t.get('id') for t in p['tables']}
        for x in p['people']:
            a=amap.get(x['id'])
            if a:
                tid=a.get('table_id')
                x['table_id']=tid if tid in valid else None
                x['seat']=a.get('seat') if tid in valid else None
    touch(p);return state()

@app.post('/api/benches')
def add_bench():
    p=project(); d=request.get_json(force=True); count=max(2,min(30,int(d.get('count',5))))
    x=float(d.get('x',50));y=float(d.get('y',50));spacing=float(d.get('spacing',3.2));rotation=float(d.get('rotation',0))
    bench_id=uid('bench'); created=[]
    import math
    rad=math.radians(rotation); dx=math.cos(rad)*spacing;dy=math.sin(rad)*spacing
    start=(count-1)/2
    for i in range(count):
        sx=max(2,min(98,x+(i-start)*dx));sy=max(3,min(97,y+(i-start)*dy))
        t={'id':uid('t'),'name':f'ספסל {bench_id[-4:]} · מקום {i+1}','x':sx,'y':sy,'capacity':1,
           'rank':float(d.get('rank',max(1,round(y/10,1)))),'custom_rank':False,'locked':False,'kind':'seat','shape':'chair',
           'rotation':rotation,'w':0,'h':0,'bench_id':bench_id,'bench_index':i+1}
        p['tables'].append(t);created.append(t['id'])
    touch(p);return jsonify(created=created,**state().get_json())

@app.post('/api/hall-objects')
def add_hall_object():
    p=project();d=request.get_json(force=True);p.setdefault('hall_objects',[])
    o={'id':uid('o'),'kind':d.get('kind','zone'),'name':str(d.get('name') or 'אובייקט'),'x':float(d.get('x',50)),'y':float(d.get('y',50)),
       'w':float(d.get('w',20)),'h':float(d.get('h',8)),'rotation':float(d.get('rotation',0))}
    p['hall_objects'].append(o);touch(p);return state()
@app.patch('/api/hall-objects/<oid>')
def edit_hall_object(oid):
    p=project();o=next((o for o in p.setdefault('hall_objects',[]) if o['id']==oid),None)
    if not o:return jsonify(error='object not found'),404
    cols=max(5,int(p.get('settings',{}).get('grid_cols',26))); rows=max(5,int(p.get('settings',{}).get('grid_rows',16)))
    d=request.get_json(force=True)
    if 'name' in d:o['name']=str(d['name'])
    for k in ('x','y','w','h','rotation'):
        if k in d:o[k]=float(d[k])
    for k in ('gx','gy','gw','gh'):
        if k in d:o[k]=int(d[k])
    if o.get('gx') is not None:
        o['x']=(o['gx']+int(o.get('gw',1))/2)/cols*100;o['y']=(o['gy']+int(o.get('gh',1))/2)/rows*100
        o['w']=int(o.get('gw',1))/cols*100;o['h']=int(o.get('gh',1))/rows*100
    touch(p);return state()
@app.delete('/api/hall-objects/<oid>')
def delete_hall_object(oid):
    p=project();p['hall_objects']=[o for o in p.setdefault('hall_objects',[]) if o['id']!=oid];touch(p);return state()

@app.post('/api/groups')
def add_group():
    p=project(); d=request.get_json(force=True); name=(d.get('name') or '').strip()
    if not name:return jsonify(error='חסר שם קבוצה'),400
    if any(g['name']==name for g in p['groups']):return jsonify(error='הקבוצה כבר קיימת'),400
    p['groups'].append({'id':uid('g'),'name':name,'priority':len(p['groups'])+1}); touch(p); return state()
@app.post('/api/groups/reorder')
def reorder_groups():
    p=project(); order=request.get_json(force=True).get('order',[]); mp={g['id']:g for g in p['groups']}
    p['groups']=[mp[i] for i in order if i in mp]+[g for g in p['groups'] if g['id'] not in order]
    renumber_groups(p); touch(p); return state()
@app.delete('/api/groups/<gid>')
def delete_group(gid):
    p=project()
    if any(x.get('group_id')==gid for x in p['people']): return jsonify(error='הקבוצה עדיין מכילה אנשים'),400
    p['groups']=[g for g in p['groups'] if g['id']!=gid]; renumber_groups(p); touch(p); return state()

@app.post('/api/people')
def add_person():
    p=project(); d=request.get_json(force=True); name=(d.get('name') or '').strip(); gid=d.get('group_id')
    if not name:return jsonify(error='חסר שם'),400
    if any(x['name']==name for x in p['people']):return jsonify(error='השם כבר קיים'),400
    if gid and not group_by_id(p,gid):return jsonify(error='group not found'),400
    p['people'].append({'id':uid('u'),'name':name,'group_id':gid,'table_id':None,'seat':None,'locked':False,'note':'','preferred_zone':'','preferred_tags':[],'seat_preference':'project'}); touch(p); return state()
@app.patch('/api/people/<pid>')
def edit_person(pid):
    p=project(); x=person_by_id(p,pid)
    if not x:return jsonify(error='person not found'),404
    d=request.get_json(force=True)
    for k in ('name','group_id','note','preferred_zone','seat_preference'):
        if k in d:x[k]=d[k]
    if 'locked' in d:x['locked']=bool(d['locked'])
    if 'preferred_tags' in d:x['preferred_tags']=d['preferred_tags'] if isinstance(d['preferred_tags'],list) else []
    touch(p); return state()
@app.delete('/api/people/<pid>')
def delete_person(pid):
    p=project(); p['people']=[x for x in p['people'] if x['id']!=pid]
    for r in p['rules']:r['people']=[i for i in r.get('people',[]) if i!=pid]
    p['rules']=[r for r in p['rules'] if r.get('people')]; touch(p); return state()
@app.post('/api/people/upload')
def upload_people():
    p=project(); f=request.files.get('file')
    if not f:return jsonify(error='לא נבחר קובץ'),400
    data=f.read()
    if not data:return jsonify(error='קובץ ה-CSV ריק'),400
    raw=None; used_encoding=None
    for enc in ('utf-8-sig','utf-8','cp1255','utf-16'):
        try: raw=data.decode(enc); used_encoding=enc; break
        except UnicodeDecodeError: pass
    if raw is None:return jsonify(error='לא הצלחתי לקרוא את קידוד קובץ ה-CSV'),400
    try:
        sample=raw[:4096]
        try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
        except csv.Error: dialect=csv.excel
        rows=list(csv.reader(io.StringIO(raw),dialect))
    except Exception as e:
        return jsonify(error='מבנה CSV לא תקין',details=str(e)),400
    added=0; skipped=0; created_groups=0
    headers={'name','full name','שם','שם מלא','שם המוזמן','מוזמן','שם אורח'}
    group_headers={'group','קבוצה','קבוצות','שיעור','אברכים'}
    existing={str(x.get('name','')).strip() for x in p['people']}
    for index,row in enumerate(rows,1):
        if not row or not any(str(v).strip() for v in row):continue
        name=str(row[0]).strip().lstrip('\ufeff'); gname=str(row[1]).strip() if len(row)>1 else ''
        if index==1 and (name.lower() in headers or gname.lower() in group_headers):
            continue
        if not name or name in existing: skipped+=1; continue
        gid=None
        if gname:
            g=next((g for g in p['groups'] if str(g.get('name','')).strip()==gname),None)
            if not g:
                g={'id':uid('g'),'name':gname,'priority':len(p['groups'])+1};p['groups'].append(g);created_groups+=1
            gid=g['id']
        p['people'].append({'id':uid('u'),'name':name,'group_id':gid,'table_id':None,'seat':None,'locked':False,'note':'','preferred_zone':'','preferred_tags':[],'seat_preference':'project'})
        existing.add(name);added+=1
    touch(p)
    return jsonify(added=added,skipped=skipped,created_groups=created_groups,rows=len(rows),encoding=used_encoding,**state().get_json())

@app.post('/api/seat')
def seat():
    p=project(); d=request.get_json(force=True); x=person_by_id(p,d.get('person_id'))
    if not x:return jsonify(error='person not found'),404
    tid=d.get('table_id')
    if tid is None:
        if x.get('locked'):return jsonify(error='האדם נעול למקומו'),400
        x['table_id']=None;x['seat']=None;touch(p);return state()
    t=table_by_id(p,tid)
    if not t:return jsonify(error='table not found'),404
    seat=d.get('seat'); seat=int(seat) if seat is not None else free_seat(p,t)
    if seat is None or seat<0 or seat>=t['capacity']:return jsonify(error='אין מקום פנוי'),400
    occ=next((o for o in p['people'] if o.get('table_id')==tid and o.get('seat')==seat and o['id']!=x['id']),None)
    if occ and occ.get('locked'):return jsonify(error='המקום תפוס על ידי אדם נעול'),400
    old=(x.get('table_id'),x.get('seat')); x['table_id']=tid;x['seat']=seat
    if occ:occ['table_id'],occ['seat']=old
    touch(p);return state()

@app.post('/api/rules')
def add_rule():
    p=project(); d=request.get_json(force=True); typ=d.get('type'); people=d.get('people',[])
    if typ not in ('together','separate','at_table','not_table'):return jsonify(error='סוג כלל לא תקין'),400
    if not people:return jsonify(error='יש לבחור אנשים לכלל'),400
    p['rules'].append({'id':uid('r'),'type':typ,'level':d.get('level','soft'),'people':people,'table_id':d.get('table_id')}); touch(p);return state()
@app.delete('/api/rules/<rid>')
def delete_rule(rid):
    p=project();p['rules']=[r for r in p['rules'] if r['id']!=rid];touch(p);return state()

@app.post('/api/assign')
def assign():
    p=project()
    for x in p['people']:
        if not x.get('locked') and not (x.get('table_id') and (table_by_id(p,x['table_id']) or {}).get('locked')):
            x['table_id']=None;x['seat']=None
    gp={g['id']:g['priority'] for g in p['groups']}
    pending=[x for x in p['people'] if not x.get('table_id')]
    pending.sort(key=lambda x:(gp.get(x.get('group_id'),999),x['name'])); un=[]
    for x in pending:
        candidates=[]
        for t in p['tables']:
            if t.get('locked') or free_seat(p,t) is None:continue
            score=score_candidate(p,x,t,gp.get(x.get('group_id'),999))
            if score is None:continue
            candidates.append((score,t))
        if not candidates:un.append(x['name']);continue
        candidates.sort(key=lambda z:z[0]); t=candidates[0][1]; x['table_id']=t['id'];x['seat']=free_seat(p,t)
    touch(p);return jsonify(unseated=un,**state().get_json())
@app.post('/api/reset')
def reset():
    p=project()
    for x in p['people']:
        if not x.get('locked'):x['table_id']=None;x['seat']=None
    touch(p);return state()

@app.post('/api/snapshots')
def snapshot():
    p=project(); d=request.get_json(force=True)
    snap={'id':uid('s'),'name':(d.get('name') or f"גרסה {len(p['snapshots'])+1}").strip(),'created':now(),
          'people':copy.deepcopy(p['people']),'tables':copy.deepcopy(p['tables']),'hall':copy.deepcopy(p['hall']),'hall_objects':copy.deepcopy(p.get('hall_objects',[])),'groups':copy.deepcopy(p['groups']),'rules':copy.deepcopy(p['rules'])}
    p['snapshots'].append(snap);touch(p);return state()
@app.post('/api/snapshots/<sid>/restore')
def restore_snapshot(sid):
    p=project();s=next((s for s in p['snapshots'] if s['id']==sid),None)
    if not s:return jsonify(error='snapshot not found'),404
    for k in ('people','tables','groups','rules'):
        p[k]=copy.deepcopy(s[k])
    if 'hall' in s:p['hall']=copy.deepcopy(s['hall'])
    if 'hall_objects' in s:p['hall_objects']=copy.deepcopy(s['hall_objects'])
    touch(p);return state()

@app.get('/api/export')
def export_csv():
    p=project(); out=io.StringIO();out.write('\ufeff');w=csv.writer(out);w.writerow(['שם','קבוצה','שולחן','מקום','דירוג','נעול'])
    gm={g['id']:g['name'] for g in p['groups']};tm={t['id']:t for t in p['tables']}
    for x in sorted(p['people'],key=lambda x:(tm.get(x.get('table_id'),{}).get('rank',99999),x.get('seat') or 0,x['name'])):
        t=tm.get(x.get('table_id'));w.writerow([x['name'],gm.get(x.get('group_id'),''),t['name'] if t else '',(x.get('seat')+1) if x.get('seat') is not None else '',round(effective_rank(p,t),2) if t else '', 'כן' if x.get('locked') else ''])
    r=Response(out.getvalue(),mimetype='text/csv; charset=utf-8');r.headers['Content-Disposition']='attachment; filename=hall-seating.csv';return r
@app.get('/api/backup')
def backup():
    r=Response(json.dumps(STATE,ensure_ascii=False,indent=2),mimetype='application/json');r.headers['Content-Disposition']='attachment; filename=hall-seating-backup.json';return r
@app.post('/api/backup')
def restore_backup():
    global STATE
    f=request.files.get('file')
    if not f:return jsonify(error='לא נבחר קובץ'),400
    try:s=json.load(f)
    except Exception:return jsonify(error='קובץ גיבוי לא תקין'),400
    if not isinstance(s,dict) or 'projects' not in s:return jsonify(error='מבנה גיבוי לא תקין'),400
    STATE=s;save(STATE);return state()

if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=False)
