import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
from scipy.spatial import cKDTree
A=fd.load('export2.json.gz'); B=fd.load('reborn/export_new.json.gz')
ra,ba,da=fs.prepare(A); rb,bb,db=fs.prepare(B)
toA=lambda p: p[:,[1,2,0]]
LA=ba.deform(ra.rest); RB=toA(bb.deform(rb.rest)); dressA=da.deform(ra.rest)
SA=fs.BodySurface(LA,ba.tris); SR=fs.BodySurface(RB,bb.tris)
VIS=np.load('out/shell_labels.npy')!=2
D=pickle.load(open('reborn/deform.pkl','rb'))['dispA']
gap0,_,_=SA.signed_distance(dressA)                       # original gap on Legacy
target=np.clip(gap0,0.2,1.0)                               # keep the original gap, at most 1 cm needed
up=ra.axes['up']; fwd=ra.axes['forward']
y=dressA[:,1]
s,_,_=SR.signed_distance(dressA+D); bad=(s<-0.2)&VIS
for nm,sel in (('Brust',y>125),('Taille/Bauch',(y>105)&(y<=125)),('Huefte/Po',(y>85)&(y<=105)),('Oberschenkel',(y>53)&(y<=85)),('Unterschenkel',y<=53)):
    print('%-14s im Body %5d (vorn %d, hinten %d), tiefste %.1f cm'%(nm,(bad&sel).sum(),(bad&sel&((dressA@fwd)>0)).sum(),(bad&sel&((dressA@fwd)<=0)).sum(),-s[bad&sel].min() if (bad&sel).any() else 0))
links=np.vstack([da.edges, cKDTree(dressA).query_pairs(2.0,output_type='ndarray')]); dg=np.bincount(links.ravel(),minlength=len(dressA)).astype(float)
def smooth(F,it):
    for _ in range(it):
        acc=np.zeros_like(F); np.add.at(acc,links[:,0],F[links[:,1]]); np.add.at(acc,links[:,1],F[links[:,0]])
        F=0.5*F+0.5*acc/np.maximum(dg,1)[:,None] if F.ndim==2 else 0.5*F+0.5*acc/np.maximum(dg,1)
    return F
amount=np.zeros(len(dressA))
for p in range(12):
    s,_,nR=SR.signed_distance(dressA+D)
    need=np.clip(target-s,0,3.0)
    amount=amount+smooth(need,40)
    E=smooth(nR*amount[:,None],30)
    s2,_,_=SR.signed_distance(dressA+D+E)
    print('Durchgang %d: im Body %d'%(p,((s2<-0.2)&VIS).sum()))
    if ((s2<-0.2)&VIS).sum()<50: break
new=dressA+D+E
s,_,_=SR.signed_distance(new); v=s[VIS]
print('Ergebnis: im Body %d | Abstand p10 %.2f p50 %.2f cm (Original auf Legacy: p10 %.2f p50 %.2f)'%((v<-0.2).sum(),*np.percentile(v,[10,50]),*np.percentile(gap0[VIS],[10,50])))
T=D+E; print('Gesamtverschiebung p50 %.2f p95 %.2f max %.2f cm'%tuple(np.percentile(np.linalg.norm(T,axis=1),[50,95,100])))
e=da.edges; L0=np.linalg.norm(dressA[e[:,0]]-dressA[e[:,1]],axis=1); L1=np.linalg.norm(new[e[:,0]]-new[e[:,1]],axis=1)
print('Kantendehnung p99 %.1f%%'%(100*np.percentile(np.abs(L1/np.maximum(L0,1e-4)-1),99)))
pickle.dump({'new':new,'disp':T}, open('reborn/deform2.pkl','wb'))
