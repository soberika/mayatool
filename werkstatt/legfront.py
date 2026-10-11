import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base=dress.weights; fwd=rig.axes['forward']; left=rig.axes['left']
VIS = np.load('out/shell_labels.npy') != 2
o = pickle.load(open('out/v4.pkl','rb'))['v4b hinten hoeher+vorn 5']
knee_y = rig.position('mKneeLeft')[1]; hip_y = rig.position('mHipLeft')[1]
rest = dress.deform(rig.rest, base, o); cz=rig.position('mPelvis')@fwd
front = (rest@fwd - cz) > 0; xr = rest@left
iK=rig.index['mKneeLeft']; iKr=rig.index['mKneeRight']
for s,c in ((1.0,0),(1.3,8),(1.5,14)):
  for p in range(0,100,10):
    W=rig.pose(fs.gait_pose(p,s,c)); m=fs.measure(body,dress,W,base,o); bad=(m['signed']<-0.2)&VIS&front&(m['dress'][:,1]<hip_y)
    lf = W[iK,3,:3]@fwd > W[iKr,3,:3]@fwd
    print(s,c,p,'vorn:', 'L' if lf else 'R', 'Clip vorn links-Seite %4d rechts-Seite %4d tief %.1f'%((bad&(xr>0)).sum(),(bad&(xr<0)).sum(), -m['signed'][bad].min() if bad.any() else 0))
# slit location: lining/labels near front?
lab=np.load('out/shell_labels.npy')
for L in np.unique(lab):
    s=lab==L
    if s.sum()>100: print('Teil',L,s.sum(),'x %.1f..%.1f'%(xr[s].min(),xr[s].max()),'y %.1f..%.1f'%(rest[s,1].min(),rest[s,1].max()))
