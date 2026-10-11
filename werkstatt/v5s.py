import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base=dress.weights.copy(); fwd=rig.axes['forward']; left=rig.axes['left']
VIS = np.load('out/shell_labels.npy') != 2
v4 = pickle.load(open('out/v4.pkl','rb'))['v4b hinten hoeher+vorn 5']
knee_y = rig.position('mKneeLeft')[1]; hip_y = rig.position('mHipLeft')[1]
chest_y = rig.position('mChest')[1]; neck_y = rig.position('mNeck')[1]
rest = dress.deform(rig.rest, base, v4); cz = rig.position('mChest')@fwd
bust = (rest[:,1] > chest_y-14) & (rest[:,1] < neck_y-6) & ((rest@fwd - cz) > -4)
train = [fs.gait_pose(p, s, c) for s in (1.0,1.3,1.5) for c in (0,8,14) for p in range(0,100,10)]
# Leg: same as v4, only the front flare may go further (5 -> 6.5 cm)
off = fs.local_flare(rig, body, dress, base, train, limit=6.5, above_knee=hip_y-knee_y-5.0, front_margin=6.0, fade=45, passes=8, base_offsets=v4, direction='front')[0]
# Bust: fixed 8 mm distance in the rest shape
off = fs.region_clearance(rig, body, dress, base, [rig.rest], bust, clearance=0.8, limit=1.2, passes=4, base_offsets=off)[0]
off = fs.harmonize_offsets(rig, dress, base, off, 2.0, 20)
test = [rig.pose(fs.gait_pose(p, s, c, t)) for s,c,t in ((1.4,10,5),(1.6,12,0),(1.2,16,5)) for p in (5,25,45,65,85)]
pz = rig.position('mPelvis')@fwd; front = ((rest@fwd - pz) > 0) & (rest[:,1] < hip_y)
for lab,o in (('v4 mild',v4),('v5',off)):
    n=0
    for w in test:
        m=fs.measure(body,dress,w,base,o); n+=((m['signed']<-0.2)&VIS&front).sum()
    r=dress.deform(rig.rest,base,o); s=np.abs(r[:,1]-(chest_y+3))<1.5; t=np.abs(r[:,1]-80)<1.5
    mb=fs.measure(body,dress,rig.rest,base,o)['signed'][bust&VIS]
    print('%-8s Bein vorn Clipping %5d | Brust min. Abstand %.2f cm | Brust B %.1f T %.1f | 80cm T %.1f'%(lab,n,mb.min(),np.ptp(r[s]@left),np.ptp(r[s]@fwd),np.ptp(r[t]@fwd)),flush=True)
pickle.dump({'v5':off}, open('out/v5.pkl','wb'))
fs.save_result('/home/user/mayatool/mcd_kleid_v5.json.gz', d, dress, base, off, {'rezept':'v4 mild + vorn 6.5 + Brust 8mm'}, {})
print('gespeichert')
