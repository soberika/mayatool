import sys, pickle; sys.path.insert(0,'/home/user/mayatool')
import numpy as np, mcd_fit_data as fd, mcd_fit_solver as fs
from scipy.spatial import cKDTree
A=fd.load('export2.json.gz'); B=fd.load('reborn/export_new.json.gz')
ra,ba,da=fs.prepare(A); rb,bb,db=fs.prepare(B)
toA=lambda p: p[:,[1,2,0]]; toB=lambda p: p[:,[2,0,1]]
LA=ba.deform(ra.rest); RB=toA(bb.deform(rb.rest))
dressA=da.deform(ra.rest); dressB=toA(db.deform(rb.rest))
print('Kleid A vs B (Achsen angeglichen): max %.3f cm'%np.abs(dressA-dressB).max())
SA=fs.BodySurface(LA,ba.tris); SR=fs.BodySurface(RB,bb.tris)
# Legacy body -> Reborn surface
d, near, nR = SR.signed_distance(LA, k=6)
dotn=(SA.normals*nR).sum(1)
valid=(near<9.0)&(dotn>0.3)&(LA[:,1]>RB[:,1].min()+2)&(LA[:,1]<RB[:,1].max()-2)
u=np.where(valid[:,None], -d[:,None]*nR, 0.0)
print('Legacy-Body: gueltige Zuordnung %.0f%%, Verschiebung p50 %.2f p95 %.2f max %.2f cm'%(100*valid.mean(),*np.percentile(np.linalg.norm(u[valid],axis=1),[50,95,100])))
# spatial smoothing + fill on the Legacy body (radius 2.5 cm)
pairs=cKDTree(LA).query_pairs(2.5,output_type='ndarray')
deg=np.bincount(pairs.ravel(),minlength=len(LA)).astype(float)
w=valid.astype(float); U=u*w[:,None]
for it in range(15):
    accU=np.zeros_like(U); accW=np.zeros_like(w)
    np.add.at(accU,pairs[:,0],U[pairs[:,1]]); np.add.at(accU,pairs[:,1],U[pairs[:,0]])
    np.add.at(accW,pairs[:,0],w[pairs[:,1]]); np.add.at(accW,pairs[:,1],w[pairs[:,0]])
    U=0.5*U+0.5*accU/np.maximum(deg,1)[:,None]; w=0.5*w+0.5*accW/np.maximum(deg,1)
field=U/np.maximum(w,1e-6)[:,None]; field[w<1e-4]=0
pickle.dump({'field':field,'w':w}, open('reborn/field.pkl','wb'))
# dress: kernel average of the field at nearby body points
dist,idx=SA.tree.query(dressA,k=24)
sig=np.maximum(dist[:,:1],1.0)*1.5
kw=np.exp(-(dist/sig)**2)*w[idx]
disp=(field[idx]*kw[:,:,None]).sum(1)/np.maximum(kw.sum(1),1e-9)[:,None]
newA=dressA+disp
# harmonize across mesh parts (like harmonize_offsets) in world space
links=np.vstack([da.edges, cKDTree(dressA).query_pairs(2.0,output_type='ndarray')])
dg=np.bincount(links.ravel(),minlength=len(dressA)).astype(float); D=disp.copy()
for it in range(20):
    acc=np.zeros_like(D); np.add.at(acc,links[:,0],D[links[:,1]]); np.add.at(acc,links[:,1],D[links[:,0]])
    D=0.5*D+0.5*acc/np.maximum(dg,1)[:,None]
newA=dressA+D
VIS=np.load('out/shell_labels.npy')!=2
def stats(lab,body_surf,pts):
    s,_,_=body_surf.signed_distance(pts); v=s[VIS]
    print('%-30s im Body (>2mm) %5d | Abstand p10 %.2f p50 %.2f cm'%(lab,(v<-0.2).sum(),*np.percentile(v,[10,50])))
stats('Original auf Legacy',SA,dressA); stats('Original auf Reborn (ohne Deform)',SR,dressA); stats('Deformiert auf Reborn',SR,newA)
print('Verschiebung Kleid p50 %.2f p95 %.2f max %.2f cm'%tuple(np.percentile(np.linalg.norm(D,axis=1),[50,95,100])))
e=da.edges; L0=np.linalg.norm(dressA[e[:,0]]-dressA[e[:,1]],axis=1); L1=np.linalg.norm(newA[e[:,0]]-newA[e[:,1]],axis=1)
print('Kantendehnung p99 %.1f%%, max Laengung %.2f mm'%(100*np.percentile(np.abs(L1/np.maximum(L0,1e-4)-1),99),10*np.max(L1-L0)))
pickle.dump({'newA':newA,'dispA':D}, open('reborn/deform.pkl','wb'))
