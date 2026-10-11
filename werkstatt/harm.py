import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
from scipy.spatial import cKDTree
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base = dress.weights; lab = np.load('/tmp/claude-0/fit/out/shell_labels.npy'); knee_y = rig.position('mKneeLeft')[1]
off0 = pickle.load(open('/tmp/claude-0/fit/out/aline.pkl','rb'))['A-Linie Saum 53 cm ab 86']
r0 = dress.deform(rig.rest)
pairs = cKDTree(r0).query_pairs(1.0, output_type='ndarray'); cross = pairs[lab[pairs[:,0]] != lab[pairs[:,1]]]
e = dress.edges; L0 = np.linalg.norm(r0[e[:,0]]-r0[e[:,1]],axis=1)
out = {}
for lab_, off in (('vorher', off0), ('harmonisiert r1.2', fs.harmonize_offsets(rig, dress, base, off0, 1.2, 12)), ('harmonisiert r2.0', fs.harmonize_offsets(rig, dress, base, off0, 2.0, 20))):
    disp = dress.deform(rig.rest, base, off) - r0
    dd = np.linalg.norm(disp[cross[:,0]] - disp[cross[:,1]], axis=1)
    worst = []
    for s in (1.0, 1.25, 1.4):
        t1 = 0; gap = 0
        for p in (5,10,15,20,25,45,50,55,60,65,70,75,85):
            W = rig.pose(fs.gait_pose(p, s)); m1 = fs.measure(body, dress, W, base, off)
            below = m1['dress'][:,1] < knee_y; t1 += (m1['signed'][below] < -0.2).sum()
            q = m1['dress']; q0 = dress.deform(W, base)
            gap = max(gap, np.abs(np.linalg.norm(q[cross[:,0]]-q[cross[:,1]],axis=1) - np.linalg.norm(q0[cross[:,0]]-q0[cross[:,1]],axis=1)).max())
        worst.append('x%.2f Wade %d, Teil-Abstand max %.1f cm' % (s, t1, gap))
    r1 = r0 + disp; L1 = np.linalg.norm(r1[e[:,0]]-r1[e[:,1]],axis=1)
    print('%-18s Teile-Versatz Ruhe p95 %.2f max %.2f cm | %s | Dehnung p99 %.0f%%' % (lab_, np.percentile(dd,95), dd.max(), ' | '.join(worst), 100*np.percentile((L1-L0)/np.maximum(L0,0.05),99)))
    out[lab_] = off
pickle.dump(out, open('/tmp/claude-0/fit/out/harm.pkl','wb'))
