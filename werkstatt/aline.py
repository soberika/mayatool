import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, mcd_fit_data as fd, mcd_fit_solver as fs
d = fd.load('/tmp/claude-0/fit/export2.json.gz'); rig, body, dress = fs.prepare(d)
base = dress.weights.copy(); knee_y = rig.position('mKneeLeft')[1]
flare = pickle.load(open('/tmp/claude-0/fit/out/flare4.pkl','rb'))['hinten 7.5 / vorn 2.0']
variants = {'0.5.3': None}
prev = pickle.load(open('/tmp/claude-0/fit/out/column.pkl','rb'))['Saeule 45 cm + 7,5/2']
variants['Saeule (letzte)'] = fs.fill_back_line(rig, dress, base, 95.0, base_offsets=prev)
for hem_w, start in ((49.0, 65.0), (52.0, 70.0), (53.0, 86.0)):
    off = fs.column_hem(rig, dress, base, start, hem_w/2, base_offsets=flare, smooth=30)
    off = fs.fill_back_line(rig, dress, base, 95.0, base_offsets=off)
    variants['A-Linie Saum %.0f cm ab %.0f' % (hem_w, start)] = off
e = dress.edges; r0 = dress.deform(rig.rest); L0 = np.linalg.norm(r0[e[:,0]]-r0[e[:,1]],axis=1)
# reference ratios (front view, normalised to width just below the hands, t=0.25)
ref_t = np.array([0.25, 0.5, 0.7, 0.85]); ref_r = np.array([0.72, 0.78, 0.84, 0.90]) / 0.72
ref_back = np.array([0.77, 0.84, 0.89, 0.93]) / 0.77
prof = {}
for lab, off in variants.items():
    r1 = dress.deform(rig.rest, base, off); L1 = np.linalg.norm(r1[e[:,0]]-r1[e[:,1]],axis=1); rel = (L1-L0)/np.maximum(L0,0.05)
    ys = np.arange(9, 100, 1.0); w = []; bk = []
    for y in ys:
        s = (r1[:,1]>=y)&(r1[:,1]<y+1); w.append(np.ptp(r1[s,0]) if s.sum()>3 else np.nan); bk.append(r1[s,2].min() if s.sum()>3 else np.nan)
    w = np.array(w); hip_y, hem_y = 92.0, 9.0
    t = (hip_y - ys) / (hip_y - hem_y); w25 = np.interp(0.25, t[::-1], w[::-1])
    prof[lab] = (t, w / w25, ys, w, np.array(bk))
    tot = []
    for s in (1.0, 1.25, 1.4):
        t1 = 0
        for p in (5,10,15,20,25,45,50,55,60,65,70,75,85):
            W = rig.pose(fs.gait_pose(p, s)); m1 = fs.measure(body, dress, W, base, off)
            below = m1['dress'][:,1] < knee_y; t1 += (m1['signed'][below] < -0.2).sum()
        tot.append(t1)
    print('%-22s Wade %s | Saum/Oberschenkel-Breite %.2f (Referenz 1,25) | Dehnung p99 %.0f%%' % (lab, tot, np.interp(0.85, t[::-1], (w/w25)[::-1]), 100*np.percentile(rel,99)))
    variants[lab] = off
pickle.dump(variants, open('/tmp/claude-0/fit/out/aline.pkl','wb'))
fig, axes = plt.subplots(1, 2, figsize=(10, 6))
cols = ['#333333', '#3b7dd8', '#2a9d8f', '#d0547a', '#7b2cbf']
for c, (lab, (t, ratio, ys, w, bk)) in zip(cols, prof.items()):
    sel = (t >= 0.2) & (t <= 0.9)
    axes[0].plot(t[sel], ratio[sel], color=c, lw=2, label=lab)
    axes[1].plot(w/2, ys, color=c, lw=2, label=lab); axes[1].plot(-w/2, ys, color=c, lw=2)
axes[0].plot(ref_t, ref_r, 'o--', color='#c9a227', lw=2, label='Referenzbild (vorn)')
axes[0].plot(ref_t, ref_back, 's:', color='#c9a227', lw=1.5, label='Referenzbild (hinten)')
axes[0].set_xlabel('von Oberschenkel (0,25) bis Saum (0,85)'); axes[0].set_ylabel('Breite relativ zum Oberschenkel'); axes[0].legend(fontsize=7); axes[0].grid(alpha=0.3)
axes[0].set_title('Form-Vergleich mit dem Referenzbild', fontsize=9)
axes[1].set_aspect('equal'); axes[1].grid(alpha=0.3); axes[1].set_title('Breite von vorn (cm)', fontsize=9); axes[1].legend(fontsize=7, loc='lower center')
plt.tight_layout(); plt.savefig('/home/user/mayatool/ausstellen_aline.png', dpi=100)
