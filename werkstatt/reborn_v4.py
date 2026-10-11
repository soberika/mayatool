import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/reborn/export_rig.json.gz'); rig, body, dress = fs.prepare(d)
base = dress.weights.copy(); up = rig.axes['up']
VIS = np.load('/tmp/claude-0/fit/out/shell_labels.npy') != 2
knee_y = rig.position('mKneeLeft') @ up; hip_y = rig.position('mHipLeft') @ up
print('knee %.1f hip %.1f axes'%(knee_y,hip_y), {k:np.round(v,2) for k,v in rig.axes.items()}, flush=True)
train = [fs.gait_pose(p, s, c) for s in (1.0, 1.3, 1.5) for c in (0, 8, 14) for p in range(0,100,10)]
test = [rig.pose(fs.gait_pose(p, s, c, t)) for s, c, t in ((1.0,0,0),(1.4,10,5),(1.6,12,0),(1.2,16,5)) for p in (5,25,45,65,85)]
def report(lab, off):
    calf=thigh=0
    for W in test:
        m=fs.measure(body,dress,W,base,off); y=m['dress']@up; bad=(m['signed']<-0.2)&VIS
        calf+=(bad&(y<knee_y)).sum(); thigh+=(bad&(y>=knee_y)&(y<hip_y)).sum()
    r=fs.measure(body,dress,rig.rest,base,off)['signed'][VIS]
    print('%-22s Wade %5d Oberschenkel %5d | Ruhe: im Body %d'%(lab,calf,thigh,(r<-0.2).sum()),flush=True)
report('Reborn ohne Anpassung', None)
off = fs.local_flare(rig, body, dress, base, train, limit=9.0, above_knee=35.0, front_margin=8.0, fade=45, passes=10)[0]
off = fs.local_flare(rig, body, dress, base, train, limit=5.0, above_knee=hip_y-knee_y-5.0, front_margin=6.0, fade=45, passes=8, base_offsets=off, direction='front')[0]
off = fs.column_hem(rig, dress, base, 86.0, 26.5, base_offsets=off, smooth=30)
off = fs.fill_back_line(rig, dress, base, 95.0, base_offsets=off)
mild = fs.harmonize_offsets(rig, dress, base, off, 2.0, 20); report('v4 mild (Reborn)', mild)
glatt = fs.harmonize_offsets(rig, dress, base, mild, 4.0, 100); report('v4 mild sehr glatt', glatt)
pickle.dump({'mild':mild,'glatt':glatt}, open('/tmp/claude-0/fit/reborn/v4.pkl','wb'))
fs.save_result('/home/user/mayatool/mcd_kleid_reborn_v4_mild.json.gz', d, dress, base, mild, {'rezept':'v4 mild Reborn'}, {})
fs.save_result('/home/user/mayatool/mcd_kleid_reborn_v4_mild_sehr_glatt.json.gz', d, dress, base, glatt, {'rezept':'v4 mild sehr glatt Reborn'}, {})
print('gespeichert')
