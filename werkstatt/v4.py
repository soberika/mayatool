import sys, pickle, time; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base = dress.weights.copy(); fwd=rig.axes['forward']; left=rig.axes['left']
VIS = np.load('/tmp/claude-0/fit/out/shell_labels.npy') != 2
knee_y = rig.position('mKneeLeft')[1]; hip_y = rig.position('mHipLeft')[1]
train = [fs.gait_pose(p, s, c) for s in (1.0, 1.3, 1.5) for c in (0, 8, 14) for p in range(0,100,10)]
test = [fs.gait_pose(p, s, c, t) for s, c, t in ((1.0,0,0),(1.4, 10, 5), (1.6, 12, 0), (1.2, 16, 5)) for p in (5, 25, 45, 65, 85)]
v3 = pickle.load(open('/tmp/claude-0/fit/out/catwalk.pkl','rb'))['Laufsteg v3']
def build(back_above, back_lim, front_lim, margin=0.4):
    off = fs.local_flare(rig, body, dress, base, train, limit=back_lim, margin=margin, above_knee=back_above, front_margin=8.0, fade=45, passes=10)[0]
    off = fs.local_flare(rig, body, dress, base, train, limit=front_lim, margin=margin, above_knee=hip_y-knee_y-5.0, front_margin=6.0, fade=45, passes=8, base_offsets=off, direction='front')[0]
    off = fs.column_hem(rig, dress, base, 86.0, 26.5, base_offsets=off, smooth=30)
    off = fs.fill_back_line(rig, dress, base, 95.0, base_offsets=off)
    return fs.harmonize_offsets(rig, dress, base, off, 2.0, 20)
e = dress.edges; r0 = dress.deform(rig.rest); L0 = np.linalg.norm(r0[e[:,0]]-r0[e[:,1]],axis=1)
def report(lab, off):
    calf=thigh=deep=0
    for rot in test:
        m = fs.measure(body, dress, rig.pose(rot), base, off); y=m['dress'][:,1]; sd=m['signed']
        bad=(sd<-0.2)&VIS; calf+=(bad&(y<knee_y)).sum(); thigh+=(bad&(y>=knee_y)&(y<hip_y)).sum(); deep+=((sd<-0.5)&VIS&(y<hip_y)).sum()
    r1 = dress.deform(rig.rest, base, off); L1=np.linalg.norm(r1[e[:,0]]-r1[e[:,1]],axis=1); rel=(L1-L0)/np.maximum(L0,0.05)
    # silhouette: half-width and depth at thigh height 80 cm and hem 60 cm
    sil=[]
    for h in (95,80,65):
        s=np.abs(r1[:,1]-h)<1.5
        sil.append('%d: B%.1f T%.1f'%(h,np.ptp(r1[s]@left),np.ptp(r1[s]@fwd)))
    print('%-28s Wade %5d Ober %5d tief>5mm %5d | Dehnung p99 %3.0f%% | %s'%(lab,calf,thigh,deep,100*np.percentile(rel,99),'  '.join(sil)),flush=True)
report('0.5.3', None); report('v3', v3)
out={'v3':v3}
for lab,args in (('v4a hinten hoeher',(35,9.0,3.5)),('v4b hinten hoeher+vorn 5',(35,9.0,5.0)),('v4c hinten 45, vorn 5',(45,10.0,5.0))):
    t=time.time(); out[lab]=build(*args); report(lab,out[lab]); print('  %.0fs'%(time.time()-t),flush=True)
    pickle.dump(out, open('/tmp/claude-0/fit/out/v4.pkl','wb'))
