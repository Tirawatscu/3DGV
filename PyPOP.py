# This script is under prioritization of Mamostza. Don't rewrite, copy, or use for the commercial way
# Acknowledged by Tirawat^2

import numpy as np
from numpy import *


class POP():
    def __init__(self,data_v,data_x,data_y,radius,freq,length):
        self.data = data_v
        self.data_x = data_x
        self.data_y = data_y
        self.radius = radius
        self.freq = freq
        self.length = 2 * int(length/2)
        self.F = self.freq / self.length * np.arange(0, self.length/2)

    def makepop(self):
        TL = self.data.shape[0]
        for i in np.arange(0, TL-self.length, self.length/2, dtype=int):
           P = unwrap(angle(fft.fft(self.data[i:i+self.length,:]* np.hanning(self.length).reshape(self.length,1),axis=0)),axis=1)[0:int(self.length/2)]
           if i == 0:
              SN = 1
              KR = sqrt(2*(var(P,axis=1)))
           else:
              SN = SN + 1
              KR = KR + sqrt(2*(var(P,axis=1)))
        KR = KR/SN
        KR[KR == 0] = 1e-10  # replace zero with a very small value
        C  = 2*pi*self.radius*self.F/KR
        C2 = 2*pi*self.radius*self.F/(pi/1.5)
        return self.F, C, C2
    
    def makepopAmp(self):
        TL = self.data.shape[0]
        for i in np.arange(0, TL-self.length, self.length/2, dtype=int):
           P = abs(fft.fft(self.data[i:i+self.length,:]* np.hanning(self.length).reshape(self.length,1),axis=0))[0:int(self.length/2)]
           if i == 0:
              SN = 1
              KR = sqrt(2*(var(P,axis=1)))
           else:
              SN = SN + 1
              KR = KR + sqrt(2*(var(P,axis=1)))
        KR = KR/SN
        C  = KR
        C2 = KR
        return self.F, C, C2

    def pyramidPOP(self):
        TL = self.data.shape[0]
        #mainRadius = [1*self.radius, 2*self.radius, 4*self.radius]
        mainRadius = [6, 12, 24]
        r = [[0, 1, 2], [0, 3, 4], [0, 5, 6]]
        radius = self.radius
        C1 = np.zeros((int(self.length/2), 3))

        for ir, rad in enumerate(radius):
            for i in np.arange(0, TL-self.length, self.length/2, dtype=int):
                P = unwrap(angle(fft.fft(self.data[i:i+self.length, :]* np.hanning(self.length).reshape(self.length,1),axis=0)),axis=1)[0:int(self.length/2)]
                P1 = mean(P[:, [0,1,2]], axis=1)
                P2 = mean(P[:, [0,3,4]], axis=1)
                P3 = mean(P[:, [0,5,6]], axis=1)
                new_P1 = np.array([P1, P2, P[:, 1]]).T
                new_P2 = np.array([P1, P2, P[:, 2]]).T
                new_P3 = np.array([P2, P3, P[:, 3]]).T
                new_P4 = np.array([P2, P3, P[:, 4]]).T
                if i == 0:
                    SN = 1
                    KR = sqrt(2*(var(P[:, r[ir]],axis=1)))
                    if ir == 0:
                        KR1 = sqrt(2*(var(new_P1,axis=1)))
                        KR2 = sqrt(2*(var(new_P2,axis=1)))
                    if ir == 1:
                        KR3 = sqrt(2*(var(new_P3,axis=1)))
                        KR4 = sqrt(2*(var(new_P4,axis=1)))
                else:
                    SN = SN + 1
                    KR = KR + sqrt(2*(var(P[:, r[ir]],axis=1)))
                    if ir == 0:
                        KR1 = KR1 + sqrt(2*(var(new_P1,axis=1)))
                        KR2 = KR2 + sqrt(2*(var(new_P2,axis=1)))
                    if ir == 1:
                        KR3 = KR3 + sqrt(2*(var(new_P3,axis=1)))
                        KR4 = KR4 + sqrt(2*(var(new_P4,axis=1)))
            KR = KR/SN
            if ir == 0:
                KR1 = KR1/SN
                KR2 = KR2/SN
                C2  = 2*pi*rad/sqrt(3)*self.F/KR1
                C3  = 2*pi*rad/sqrt(3)*self.F/KR2
            if ir == 1:
                KR3 = KR3/SN
                KR4 = KR4/SN
                C4  = 2*pi*rad/sqrt(3)*self.F/KR3
                C5  = 2*pi*rad/sqrt(3)*self.F/KR4
            C  = 2*pi*rad*self.F/KR
            C1[:,ir] = C
        
        return self.F, C1, C2, C3, C4, C5
    
        

    def makepoplove(self):
        TL = self.data.shape[0]
        for i in np.arange(0,TL-self.length,self.length/2, dtype=int):
            FNT1 = fft.fft(self.data_x[i:i+self.length,:]* np.hanning(self.length).reshape(self.length,1),axis=0)[0:int(self.length/2)]
            FNT2 = fft.fft(self.data_y[i:i+self.length,:]* np.hanning(self.length).reshape(self.length,1),axis=0)[0:int(self.length/2)]
            '''threshold1 = np.max(np.abs(FNT1))/1000
            threshold2 = np.max(np.abs(FNT2))/1000
            FNT1temp[np.abs(FNT1)<threshold1] = 0
            FNT2temp[np.abs(FNT2)<threshold2] = 0'''
            phiN = np.angle(FNT1)
            phiT = np.angle(FNT2)
            RV = angle(fft.fft(self.data[i:i+self.length,:]* np.hanning(self.length).reshape(self.length,1),axis=0))[0:int(self.length/2)]
            print(RV)
            AN = np.abs(FNT1)
            AT = np.abs(FNT2)

            RH = RV + np.pi/2
            C = AN * np.sin(phiN - RH)
            D = AT * np.sin(phiT - RH)
            sintheta = C/sqrt(C**2 + D**2)
            costheta = D/sqrt(C**2 + D**2)
            E = AN *sintheta*np.sin(phiN) + AT*costheta*np.sin(phiT)
            F = AN *sintheta*np.cos(phiN) + AT*costheta*np.cos(phiT)
            phiL = np.arccos(E/sqrt(E**2 + F**2))
            if i == 0:
                SN = 1
                self.Kl = sqrt(2*(var(phiL.T,0)))
            else:
                SN = SN + 1
                self.Kl = self.Kl + sqrt(2*(var(phiL.T,0)))
            #print(fft.fft(data[i:i+self.length,:]))
        self.Kl = self.Kl/SN
        Cl  = 2*pi*self.radius*self.F/self.Kl[0:int(self.length/2)]
        C2 = 2*pi*self.radius*self.F/(pi/1.5)
        return self.F, Cl, C2

