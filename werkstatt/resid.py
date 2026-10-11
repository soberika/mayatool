import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base = dress.weights.copy()
fwd=rig.axes['forward']; left=rig.axes['left']
knee_y = rig.position('mKneeLeft')[1]; hip_y = rig.position('mHipLeft')[1]
VIS = np.load('/tmp/claude-0/fit/out/shell_labels.npy') != 2
v3 = pickle.load(open('/tmp/claude-0/fit/out/catwalk.pkl','rb'))['Laufsteg v3']
rest = dress.deform(rig.rest, base, v3); cz = rig.position('mPelvis')@fwd
poses = [(s,c,t,p) for s,c,t in ((1.0,0,0),(1.3,8,0),(1.5,14,0),(1.4,10,5),(1.6,12,0),(1.2,16,5)) for p in range(0,100,10)]
agg = {}
for s,c,t,p in poses:
    m = fs.measure(body, dress, rig.pose(fs.gait_pose(p,s,c,t)), base, v3)
    sd = m["signed"]; bad = (sd < -0.2) & VIS
    y = rest[:,1]; z = rest@fwd - cz; x = rest@left
    reg = np.where(y<knee_y,'Wade' ,np.where(y<hip_y,'Ober','Huefte'))
    side = np.where(z<0,'hinten','vorn'); inner = np.where(np.abs(x)<6,'innen','aussen')
    key=(s,c,t)
    for r in ('Wade','Ober','Huefte'):
      for sd_ in ('hinten','vorn'):
        for io in ('innen','aussen'):
          sel = bad&(reg==r)&(side==sd_)&(inner==io)
          if sel.any():
            a=agg.setdefault((r,sd_,io),[0,0.0,set()]); a[0]+=sel.sum(); a[1]=max(a[1],-sd[sel].min()); a[2].add(p)
for k,v in sorted(agg.items(), key=lambda kv:-kv[1][0]):
    print(k, 'Punkte', v[0], 'tiefste %.1f cm'%v[1], 'Phasen', sorted(v[2]))
print('x range', (rest@left).min(), (rest@left).max(), 'knee', knee_y, 'hip', hip_y)
