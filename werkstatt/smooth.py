import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('export2.json.gz'); rig, body, dress = fs.prepare(d); base=dress.weights.copy()
VIS = np.load('out/shell_labels.npy') != 2
knee_y = rig.position('mKneeLeft')[1]; hip_y = rig.position('mHipLeft')[1]
v4 = pickle.load(open('out/v4.pkl','rb'))['v4b hinten hoeher+vorn 5']
test = [rig.pose(fs.gait_pose(p, s, c, t)) for s,c,t in ((1.0,0,0),(1.4,10,5),(1.6,12,0),(1.2,16,5)) for p in (5,25,45,65,85)]
rest0 = dress.deform(rig.rest, base); e = dress.edges
def rough(o):
    disp = dress.deform(rig.rest, base, o) - rest0
    acc=np.zeros_like(disp); deg=np.bincount(e.ravel(),minlength=len(disp)).astype(float)
    np.add.at(acc,e[:,0],disp[e[:,1]]); np.add.at(acc,e[:,1],disp[e[:,0]])
    lap=np.linalg.norm(disp-acc/np.maximum(deg,1)[:,None],axis=1); return np.percentile(lap,99)*10
def clip(o):
    n=0
    for w in test:
        m=fs.measure(body,dress,w,base,o); n+=((m['signed']<-0.2)&VIS&(m['dress'][:,1]<hip_y)).sum()
    return n
out={}
for lab,o in (('v4 mild',v4),('glatt',fs.harmonize_offsets(rig,dress,base,v4,3.0,40)),('sehr glatt',fs.harmonize_offsets(rig,dress,base,v4,4.0,100))):
    out[lab]=o; print('%-11s Unruhe p99 %.2f mm | Clipping Beine %d'%(lab,rough(o),clip(o)),flush=True)
pickle.dump(out,open('out/smooth.pkl','wb'))
for lab,f in (('glatt','mcd_kleid_v4_mild_glatt.json.gz'),('sehr glatt','mcd_kleid_v4_mild_sehr_glatt.json.gz')):
    fs.save_result('/home/user/mayatool/'+f,d,dress,base,out[lab],{'rezept':'v4 mild '+lab},{})
print('ok')
