import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base = dress.weights.copy(); up = rig.axes['up']
knee_y = rig.position('mKneeLeft')[1]; hip_y = rig.position('mHipLeft')[1]
phases = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90)
train = [fs.gait_pose(p, s, c) for s in (1.0, 1.3, 1.5) for c in (0, 8, 14) for p in phases]
test = [fs.gait_pose(p, s, c, t) for s, c, t in ((1.4, 10, 5), (1.6, 12, 0), (1.2, 16, 5)) for p in (5, 25, 45, 65, 85)]
def score(off, poses):
    calf = thigh = 0
    for rot in poses:
        m = fs.measure(body, dress, rig.pose(rot), base, off); y = m['dress'][:,1]; bad = m['signed'] < -0.2
        calf += (bad & (y < knee_y)).sum(); thigh += (bad & (y >= knee_y) & (y < hip_y)).sum()
    return calf, thigh
prev = pickle.load(open('/tmp/claude-0/fit/out/harm.pkl','rb'))['harmonisiert r2.0']
variants = {'0.5.3': None, 'A-Linie v2 (dein Test)': prev}
# new: back flare (calves), front flare up to the hip (thighs), A-line, straight back, harmonized
off = fs.local_flare(rig, body, dress, base, train, limit=9.0, above_knee=20.0, front_margin=8.0, fade=45, passes=10)[0]
off = fs.local_flare(rig, body, dress, base, train, limit=3.5, above_knee=hip_y - knee_y - 5.0, front_margin=6.0, fade=45, passes=8, base_offsets=off, direction='front')[0]
off = fs.column_hem(rig, dress, base, 86.0, 26.5, base_offsets=off, smooth=30)
off = fs.fill_back_line(rig, dress, base, 95.0, base_offsets=off)
off = fs.harmonize_offsets(rig, dress, base, off, 2.0, 20)
variants['Laufsteg v3'] = off
e = dress.edges; r0 = dress.deform(rig.rest); L0 = np.linalg.norm(r0[e[:,0]]-r0[e[:,1]],axis=1)
for lab, o in variants.items():
    tr = score(o, train[::3]); te = score(o, test)
    if o is None: rel = np.zeros(1)
    else:
        r1 = dress.deform(rig.rest, base, o); L1 = np.linalg.norm(r1[e[:,0]]-r1[e[:,1]],axis=1); rel = (L1-L0)/np.maximum(L0,0.05)
    print('%-24s Training: Wade %5d Oberschenkel %5d | Test (nie gesehen): Wade %5d Oberschenkel %5d | Dehnung p99 %.0f%%' % (lab, tr[0], tr[1], te[0], te[1], 100*np.percentile(rel,99)))
pickle.dump(variants, open('/tmp/claude-0/fit/out/catwalk.pkl','wb'))
