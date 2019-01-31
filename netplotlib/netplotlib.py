# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import tellurium as te
import networkx as nx
from matplotlib.patches import FancyArrowPatch, Circle, FancyBboxPatch
from matplotlib.path import Path
import matplotlib.pyplot as plt
import numpy as np
from scipy import interpolate
import sympy
import tesbml
import itertools

def getVersion():
    """
    Return version
    """
    
    try:
    	with open(os.path.join(os.path.dirname(__file__), '..', 'VERSION.txt'), 'r') as f:
    		version = f.read().rstrip()
    except:
    	with open(os.path.join(os.path.dirname(__file__), 'VERSION.txt'), 'r') as f:
    		version = f.read().rstrip()
    
    return version


class Network():
    
    def __init__(self, model):
        """
        Creates a new Network object. 
        
        :param model: SBML or Antimony string of a model
        :type name: str
        """
        
        try:
            self.rrInstance = te.loadSBMLModel(model)
        except:
            try:
                self.rrInstance = te.loadAntimonyModel(model)
            except:
                raise Exception("Input does not seem to be a valid SBML or Antimony string")
                
        self.reset()
    

    def reset(self):
        """
        Resets all properties
        """
    
        self.scale = 1.25
        self.fontsize = 10
        self.edgelw = 3
        self.nodeColor = 'tab:blue'
        self.reactionNodeColor = 'tab:gray'
        self.labelColor = 'w'
        self.labelReactionIds = False
        self.reactionColor = 'k'
        self.modifierColor = 'tab:red'
        self.boundaryColor = 'tab:green'
        self.nodeEdgeColor = 'k'
        self.nodeEdgelw = 0
        self.highlight = []
        self.hlNodeColor = 'tab:purple'
        self.hlNodeEdgeColor = 'tab:pink'
        self.drawReactionNode = True
        self.breakBoundary = False


    def getLayout(self):
        """
        Return the layout of the model
        """
        numBnd = self.rrInstance.getNumBoundarySpecies()
        numFlt = self.rrInstance.getNumFloatingSpecies()
        boundaryId = self.rrInstance.getBoundarySpeciesIds()
        floatingId = self.rrInstance.getFloatingSpeciesIds()
        rid = self.rrInstance.getReactionIds()
        
        # prepare symbols for sympy
        boundaryId_sympy = [] 
        floatingId_sympy = []
        
        # Fix issues with reserved characters
        for i in range(numBnd):
            if boundaryId[i] == 'S':
                boundaryId_sympy.append('_S')
            else:
                boundaryId_sympy.append(boundaryId[i])
        
        for i in range(numFlt):
            if floatingId[i] == 'S':
                floatingId_sympy.append('_S')
            else:
                floatingId_sympy.append(floatingId[i])
        
        paramIdsStr = ' '.join(self.rrInstance.getGlobalParameterIds())
        floatingIdsStr = ' '.join(floatingId_sympy)
        boundaryIdsStr = ' '.join(boundaryId_sympy)
        comparmentIdsStr = ' '.join(self.rrInstance.getCompartmentIds())
        
        allIds = paramIdsStr + ' ' + floatingIdsStr + ' ' + boundaryIdsStr + ' ' + comparmentIdsStr
        
        avsym = sympy.symbols(allIds)
        
        # extract reactant, product, modifiers, and kinetic laws
        rct = []
        prd = []
        mod = []
        mod_target = []
        kineticLaw = []
        mod_type = []
        
        doc = tesbml.readSBMLFromString(self.rrInstance.getSBML())
        sbmlmodel = doc.getModel()
    
        for slr in sbmlmodel.getListOfReactions():
            temprct = []
            tempprd = []
            tempmod = []
            
            sbmlreaction = sbmlmodel.getReaction(slr.getId())
            for sr in range(sbmlreaction.getNumReactants()):
                sbmlrct = sbmlreaction.getReactant(sr)
                temprct.append(sbmlrct.getSpecies())
            for sp in range(sbmlreaction.getNumProducts()):
                sbmlprd = sbmlreaction.getProduct(sp)
                tempprd.append(sbmlprd.getSpecies())
            for sm in range(sbmlreaction.getNumModifiers()):
                sbmlmod = sbmlreaction.getModifier(sm)
                tempmod.append(sbmlmod.getSpecies())
            kl = sbmlreaction.getKineticLaw()
            
            if len(temprct) == 0:
                rct.append(['Input'])
            else:
                rct.append(temprct)
            if len(tempprd) == 0:
                prd.append(['Output'])
            else:
                prd.append(tempprd)
            mod.append(tempmod)
            
            # Update kinetic law according to change in species name
            kl_split = kl.getFormula().split(' ')
            for i in range(len(kl_split)):
                if kl_split[i] == 'S':
                    kl_split[i] = '_S'
                else:
                    pass
            
            kineticLaw.append(' '.join(kl_split))
        
        # use sympy for analyzing modifiers weSmart
        for ml in range(len(mod)):
            mod_type_temp = []
            expression = kineticLaw[ml]
            n,d = sympy.fraction(expression)
            for ml_i in range(len(mod[ml])):
                if n.has(mod[ml][ml_i]):
                    mod_type_temp.append('activator')
                elif d.has(mod[ml][ml_i]):
                    mod_type_temp.append('inhibitor')
                else:
                    continue
            mod_type.append(mod_type_temp)
        
        for i in range(len(mod)):
            mod_target_temp = []
            if len(mod[i]) > 0:
                mod_target_temp.append(rid[i])
            mod_target.append(mod_target_temp)
        
        if self.breakBoundary:
            speciesId = []
            boundaryId_temp = []
            bc = 0
            for i in range(len(rid)):
                for j in range(len(rct[i])):
                    if rct[i][j] in boundaryId:
                        rct[i][j] = rct[i][j] + '_' + str(bc)
                        speciesId.append(rct[i][j])
                        boundaryId_temp.append(rct[i][j])
                        bc += 1
                for k in range(len(prd[i])):
                    if prd[i][k] in boundaryId:
                        prd[i][k] = prd[i][k] + '_' + str(bc)
                        speciesId.append(prd[i][k])
                        boundaryId_temp.append(prd[i][k])
                        bc += 1
            for i in range(numFlt):
                speciesId.append(floatingId[i])
            boundaryId = boundaryId_temp
                
        # initialize directional graph
        G = nx.DiGraph()
    
        # add edges
        for i in range(sbmlmodel.getNumReactions()):
            if len(rct[i]) == 0:
                G.add_edges_from([('Input', rid[i])], weight=(1+self.edgelw))
            else:
                for k in range(len(rct[i])):
                    G.add_edges_from([(rct[i][k], rid[i])], weight=(1+self.edgelw))
            
            if len(prd[i]) == 0:
                G.add_edges_from([(rid[i], 'Output')], weight=(1+self.edgelw))
            else:
                for j in range(len(prd[i])):
                    G.add_edges_from([(rid[i], prd[i][j])], weight=(1+self.edgelw))
                        
            if len(mod[i]) > 0:
                if mod_type[i][0] == 'inhibitor':
                    G.add_edges_from([(mod[i][0], rid[i])], weight=(1+self.edgelw))
                elif mod_type[i][0] == 'activator':
                    G.add_edges_from([(mod[i][0], rid[i])], weight=(1+self.edgelw))
            
        # calcutate positions
        thres = 0.1
        shortest_dist = dict(nx.shortest_path_length(G, weight='weight'))
        pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
        
        dist_flag = True
        maxIter = 50
        maxIter_n = 0
        
        while dist_flag and (maxIter_n < maxIter):
            dist_flag = False
            for i in itertools.combinations(speciesId, 2):
                pos_dist = np.linalg.norm(pos[i[0]] - pos[i[1]])
                if pos_dist < thres:
                    dist_flag = True
                    shortest_dist[i[0]][i[1]] = 4
            pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
            maxIter_n += 1
            
        return pos
    
    
    def draw(self):
        """
        Draw network diagram
        """
        
        numBnd = self.rrInstance.getNumBoundarySpecies()
        numFlt = self.rrInstance.getNumFloatingSpecies()
        boundaryId = self.rrInstance.getBoundarySpeciesIds()
        floatingId = self.rrInstance.getFloatingSpeciesIds()
        rid = self.rrInstance.getReactionIds()
        stoch = self.rrInstance.getFullStoichiometryMatrix()
        stoch_row = stoch.rownames
        
        # prepare symbols for sympy
        boundaryId_sympy = [] 
        floatingId_sympy = []
        
        # Fix issues with reserved characters
        for i in range(numBnd):
            if boundaryId[i] == 'S':
                boundaryId_sympy.append('_S')
            else:
                boundaryId_sympy.append(boundaryId[i])
        
        for i in range(numFlt):
            if floatingId[i] == 'S':
                floatingId_sympy.append('_S')
            else:
                floatingId_sympy.append(floatingId[i])
        
        paramIdsStr = ' '.join(self.rrInstance.getGlobalParameterIds())
        floatingIdsStr = ' '.join(floatingId_sympy)
        boundaryIdsStr = ' '.join(boundaryId_sympy)
        comparmentIdsStr = ' '.join(self.rrInstance.getCompartmentIds())
        
        allIds = paramIdsStr + ' ' + floatingIdsStr + ' ' + boundaryIdsStr + ' ' + comparmentIdsStr
        
        avsym = sympy.symbols(allIds)
        
        # extract reactant, product, modifiers, and kinetic laws
        rct = []
        prd = []
        mod = []
        mod_target = []
        kineticLaw = []
        mod_type = []
        
        doc = tesbml.readSBMLFromString(self.rrInstance.getSBML())
        sbmlmodel = doc.getModel()
    
        for slr in sbmlmodel.getListOfReactions():
            temprct = []
            tempprd = []
            tempmod = []
            
            sbmlreaction = sbmlmodel.getReaction(slr.getId())
            for sr in range(sbmlreaction.getNumReactants()):
                sbmlrct = sbmlreaction.getReactant(sr)
                temprct.append(sbmlrct.getSpecies())
            for sp in range(sbmlreaction.getNumProducts()):
                sbmlprd = sbmlreaction.getProduct(sp)
                tempprd.append(sbmlprd.getSpecies())
            for sm in range(sbmlreaction.getNumModifiers()):
                sbmlmod = sbmlreaction.getModifier(sm)
                tempmod.append(sbmlmod.getSpecies())
            kl = sbmlreaction.getKineticLaw()
            
            if len(temprct) == 0:
                rct.append(['Input'])
            else:
                rct.append(sorted(temprct, key=lambda v: (v.upper(), v[0].islower())))
            if len(tempprd) == 0:
                prd.append(['Output'])
            else:
                prd.append(sorted(tempprd, key=lambda v: (v.upper(), v[0].islower())))
            mod.append(sorted(tempmod, key=lambda v: (v.upper(), v[0].islower())))
            
            # Update kinetic law according to change in species name
            kl_split = kl.getFormula().split(' ')
            for i in range(len(kl_split)):
                if kl_split[i] == 'S':
                    kl_split[i] = '_S'
            
            kineticLaw.append(' '.join(kl_split))
        
        # use sympy for analyzing modifiers weSmart
        for ml in range(len(mod)):
            mod_type_temp = []
            expression = kineticLaw[ml]
            n,d = sympy.fraction(expression)
            for ml_i in range(len(mod[ml])):
                if n.has(mod[ml][ml_i]):
                    mod_type_temp.append('activator')
                elif d.has(mod[ml][ml_i]):
                    mod_type_temp.append('inhibitor')
                else:
                    continue
            mod_type.append(mod_type_temp)
        
        for i in range(len(mod)):
            if len(mod[i]) > 0:
                mod_target.append(np.repeat(rid[i], len(mod[i])).tolist())
        
        mod_flat = [item for sublist in mod for item in sublist]
        modtype_flat = [item for sublist in mod_type for item in sublist]
        modtarget_flat = [item for sublist in mod_target for item in sublist]
        
        speciesId = list(rct + prd)
        speciesId = [item for sublist in speciesId for item in sublist]
        speciesId = list(set(speciesId))
        
        if self.breakBoundary:
            boundaryId_temp = []
            bc = 0
            for i in range(len(rid)):
                for j in range(len(rct[i])):
                    if rct[i][j] in boundaryId + ['Input', 'Output']:
                        rct[i][j] = rct[i][j] + '_' + str(bc)
                        speciesId.append(rct[i][j])
                        boundaryId_temp.append(rct[i][j])
                        bc += 1
                for k in range(len(prd[i])):
                    if prd[i][k] in boundaryId + ['Input', 'Output']:
                        prd[i][k] = prd[i][k] + '_' + str(bc)
                        speciesId.append(prd[i][k])
                        boundaryId_temp.append(prd[i][k])
                        bc += 1
            boundaryId = boundaryId_temp
                
        # initialize directional graph
        G = nx.DiGraph()
    
        # add edges
        for i in range(sbmlmodel.getNumReactions()):
            for k in range(len(rct[i])):
                G.add_edges_from([(rct[i][k], rid[i])], weight=(1+self.edgelw))
            
            for j in range(len(prd[i])):
                G.add_edges_from([(rid[i], prd[i][j])], weight=(1+self.edgelw))
                        
            if len(mod[i]) > 0:
                for l in range(len(mod[i])):
                    G.add_edges_from([(mod[i][l], rid[i])], weight=(1+self.edgelw))
            
        # calcutate positions
        thres = 0.2
        shortest_dist = dict(nx.shortest_path_length(G, weight='weight'))
        pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
        
        maxIter = 5
        s_dist_flag = True
        maxIter_n = 0
        
        while s_dist_flag and (maxIter_n < maxIter):
            s_dist_flag = False
            for i in itertools.combinations(speciesId, 2):
                pos_dist = np.linalg.norm(pos[i[0]] - pos[i[1]])
                if pos_dist < thres:
                    s_dist_flag = True
                    shortest_dist[i[0]][i[1]] = 4
            pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
            maxIter_n += 1
        
        r_dist_flag = True
        maxIter_n = 0
        
        while r_dist_flag and (maxIter_n < maxIter):
            r_dist_flag = False
            for i in itertools.combinations(speciesId + rid, 2):
                pos_dist = np.linalg.norm(pos[i[0]] - pos[i[1]])
                if pos_dist < thres:
                    r_dist_flag = True
                    shortest_dist[i[0]][i[1]] = 2
            pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
            maxIter_n += 1

#        if dist_flag:
#            pos = nx.spring_layout(G, pos=pos, scale=self.scale)
        
        # check the range of x and y positions
        max_width = []
        max_height = []
        for key, value in pos.items():
            max_width.append(value[0])
            max_height.append(value[1])
        
        max_width = [min(max_width), max(max_width)]
        max_height = [min(max_height), max(max_height)]
        
        # initialize figure
        fig = plt.figure()
        ax = plt.gca()
        
        # add nodes to the figure
        for n in G:
            if n in rid:
                rec_width = 0.05*(self.fontsize/20)
                rec_height = 0.05*(self.fontsize/20)
                if n in self.highlight:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                        rec_width, 
                                        rec_height,
                                        boxstyle="round,pad=0.01, rounding_size=0.01",
                                        linewidth=self.nodeEdgelw, 
                                        edgecolor=self.hlNodeEdgeColor, 
                                        facecolor=self.hlNodeColor)
                else:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                   rec_width, 
                                   rec_height,
                                   boxstyle="round,pad=0.01, rounding_size=0.01",
                                   linewidth=self.nodeEdgelw, 
                                   edgecolor=self.nodeEdgeColor, 
                                   facecolor=self.reactionNodeColor)
                if self.labelReactionIds:
                    plt.text(pos[n][0], pos[n][1], n, 
                         fontsize=self.fontsize, horizontalalignment='center', 
                         verticalalignment='center', color=self.labelColor)
            else:
                if len(n) > 10:
                    rec_width = max(0.045*((len(n)/2)+1), 0.13)*(self.fontsize/20)
                    rec_height = 0.20*(self.fontsize/20)
                else:
                    rec_width = max(0.045*(len(n)+1), 0.13)*(self.fontsize/20)
                    rec_height = 0.11*(self.fontsize/20)
                    
                if (n in boundaryId) or (n == 'Input') or (n == 'Output'):
                    node_color = self.boundaryColor
                else:
                    node_color = self.nodeColor
                    
                if n in self.highlight:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                       rec_width, 
                                       rec_height,
                                       boxstyle="round,pad=0.01, rounding_size=0.02",
                                       linewidth=self.nodeEdgelw, 
                                       edgecolor=self.hlNodeEdgeColor, 
                                       facecolor=self.hlNodeColor)
                else:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                       rec_width, 
                                       rec_height,
                                       boxstyle="round,pad=0.01, rounding_size=0.02",
                                       linewidth=self.nodeEdgelw, 
                                       edgecolor=self.nodeEdgeColor, 
                                       facecolor=node_color)
                if len(n) > 10:
                    plt.text(pos[n][0], pos[n][1], n[:int(len(n)/2)] + '\n' + n[int(len(n)/2):], 
                             fontsize=self.fontsize, horizontalalignment='center', 
                             verticalalignment='center', color=self.labelColor)
                else:
                    plt.text(pos[n][0], pos[n][1], n, 
                             fontsize=self.fontsize, horizontalalignment='center', 
                             verticalalignment='center', color=self.labelColor)
            G.node[n]['patch'] = c
        
        # add edges to the figure
        for i in range(len(rid)):
            if (len(rct[i]) == 1) or (len(prd[i]) == 1): # UNI-involved
                comb = list(itertools.combinations_with_replacement(rct[i],len(prd[i])))
                for j in [list(zip(x,prd[i])) for x in comb]:
                    for k in range(len(j)):
                        p1 = G.node[j[k][0]]['patch']
                        p2 = G.node[rid[i]]['patch']
                        p3 = G.node[j[k][1]]['patch']
                        
                        X1 = (p1.get_x()+p1.get_width()/2,p1.get_y()+p1.get_height()/2)
                        X2 = (p2.get_x()+p2.get_width()/2,p2.get_y()+p2.get_height()/2)
                        X3 = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height()/2)
                        
                        if (len(np.unique(rct[i])) > len(prd[i])) or (len(rct[i]) < len(np.unique(prd[i]))): # Uni-Bi or Bi-Uni
                            XY1 = np.vstack((X1, X2))
                            XY2 = np.vstack((X2, X3))
                            
                            tck1, u1 = interpolate.splprep([XY1[:,0], XY1[:,1]], k=1)
                            intX1, intY1 = interpolate.splev(np.linspace(0, 1, 100), tck1, der=0)
                            stackXY1 = np.vstack((intX1, intY1))
                            tck2, u2 = interpolate.splprep([XY2[:,0], XY2[:,1]], k=1)
                            intX2, intY2 = interpolate.splev(np.linspace(0, 1, 100), tck2, der=0)
                            stackXY2 = np.vstack((intX2, intY2))
                            
                            X3top = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height())
                            X3bot = (p3.get_x()+p3.get_width()/2,p3.get_y())
                            X3left = (p3.get_x(),p3.get_y()+p3.get_height()/2)
                            X3right = (p3.get_x()+p3.get_width(),p3.get_y()+p3.get_height()/2)
                            
                            n = -1
                            arrthres_v = .02
                            arrthres_h = .02
                            while (((stackXY2.T[n][0] > (X3left[0]-arrthres_h)) and (stackXY2.T[n][0] < (X3right[0]+arrthres_h))
                                and (stackXY2.T[n][1] > (X3bot[1]-arrthres_v)) and (stackXY2.T[n][1] < (X3top[1]+arrthres_v))) 
                                and (np.abs(n) < np.shape(stackXY2)[1] - 10)):
                                n -= 1
                           
                            lpath1 = Path(stackXY1.T)
                            lpath2 = Path(stackXY2.T[3:n])
                            
                            e1 = FancyArrowPatch(path=lpath1,
                                                arrowstyle='-',
                                                mutation_scale=10.0,
                                                lw=(1+self.edgelw),
                                                color=self.reactionColor)
                            
                            e2 = FancyArrowPatch(path=lpath2,
                                                arrowstyle='-|>',
                                                mutation_scale=10.0,
                                                lw=(1+self.edgelw),
                                                color=self.reactionColor)
                            
                            ax.add_patch(e1)
                            ax.add_patch(e2)
                            
                            if j[k][0] in floatingId:
                                if (np.abs(stoch[stoch_row.index(j[k][0])][i]) > 1):
                                    # position calculation
                                    slope = (lpath1.vertices[0][1] - lpath1.vertices[10][1])/(lpath1.vertices[0][0] - lpath1.vertices[10][0])
                                    x_prime = np.sqrt(0.01/(1 + np.square(slope)))
                                    y_prime = -slope*x_prime
                                    plt.text(x_prime+lpath1.vertices[10][0], y_prime+lpath1.vertices[10][1], int(np.abs(stoch[stoch_row.index(j[k][0])][i])), 
                                             fontsize=self.fontsize, horizontalalignment='center', 
                                             verticalalignment='center', color=self.reactionColor)
                            
                            if j[k][1] in floatingId:
                                if (np.abs(stoch[stoch_row.index(j[k][1])][i]) > 1):
                                    slope = (lpath2.vertices[0][1] - lpath2.vertices[-20][1])/(lpath2.vertices[0][0] - lpath2.vertices[-20][0])
                                    x_prime = np.sqrt(0.01/(1 + np.square(slope)))
                                    y_prime = -slope*x_prime
                                    plt.text(x_prime+lpath2.vertices[-20][0], y_prime+lpath2.vertices[-20][1], int(np.abs(stoch[stoch_row.index(j[k][1])][i])), 
                                             fontsize=self.fontsize, horizontalalignment='center', 
                                             verticalalignment='center', color=self.reactionColor)
                            
                        else: # Uni-Uni
                            XY = np.vstack((X1, X2, X3))
                            
                            tck, u = interpolate.splprep([XY[:,0], XY[:,1]], k=2)
                            intX, intY = interpolate.splev(np.linspace(0, 1, 100), tck, der=0)
                            stackXY = np.vstack((intX, intY))
                            
                            X3top = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height())
                            X3bot = (p3.get_x()+p3.get_width()/2,p3.get_y())
                            X3left = (p3.get_x(),p3.get_y()+p3.get_height()/2)
                            X3right = (p3.get_x()+p3.get_width(),p3.get_y()+p3.get_height()/2)
                            
                            n = -1
                            arrthres_v = .02
                            arrthres_h = .02
                            while (((stackXY.T[n][0] > (X3left[0]-arrthres_h)) and (stackXY.T[n][0] < (X3right[0]+arrthres_h))
                                and (stackXY.T[n][1] > (X3bot[1]-arrthres_v)) and (stackXY.T[n][1] < (X3top[1]+arrthres_v)))  
                                and (np.abs(n) < np.shape(stackXY)[1] - 10)):
                                n -= 1
                           
                            lpath = Path(stackXY.T[3:n])
                            
                            e = FancyArrowPatch(path=lpath,
                                                arrowstyle='-|>',
                                                mutation_scale=10.0,
                                                lw=(1+self.edgelw),
                                                color=self.reactionColor)
                            ax.add_patch(e)
                        
                            if j[k][0] in floatingId:
                                if (np.abs(stoch[stoch_row.index(j[k][0])][i]) > 1):
                                    slope = (lpath.vertices[0][1] - lpath.vertices[10][1])/(lpath.vertices[0][0] - lpath.vertices[10][0])
                                    x_prime = np.sqrt(0.01/(1 + np.square(slope)))
                                    y_prime = -slope*x_prime
                                    plt.text(x_prime+lpath.vertices[10][0], y_prime+lpath.vertices[10][1], int(np.abs(stoch[stoch_row.index(j[k][0])][i])), 
                                             fontsize=self.fontsize, horizontalalignment='center', 
                                             verticalalignment='center', color=self.reactionColor)
                            
                            if j[k][1] in floatingId:
                                if (np.abs(stoch[stoch_row.index(j[k][1])][i]) > 1):
                                    slope = (lpath.vertices[0][1] - lpath.vertices[-20][1])/(lpath.vertices[0][0] - lpath.vertices[-20][0])
                                    x_prime = np.sqrt(0.01/(1 + np.square(slope)))
                                    y_prime = -slope*x_prime
                                    plt.text(x_prime+lpath.vertices[-20][0], y_prime+lpath.vertices[-20][1], int(np.abs(stoch[stoch_row.index(j[k][1])][i])), 
                                             fontsize=self.fontsize, horizontalalignment='center', 
                                             verticalalignment='center', color=self.reactionColor)
                    
            else: # BIBI or larger
                for j in [list(zip(x,prd[i])) for x in itertools.combinations(rct[i],len(prd[i]))][0]:
                    p1 = G.node[j[0]]['patch']
                    p2 = G.node[rid[i]]['patch']
                    p3 = G.node[j[1]]['patch']
                    
                    X1 = (p1.get_x()+p1.get_width()/2,p1.get_y()+p1.get_height()/2)
                    X2 = (p2.get_x()+p2.get_width()/2,p2.get_y()+p2.get_height()/2)
                    X3 = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height()/2)
                    
                    XY = np.vstack((X1, X2, X3))
                    
                    tck, u = interpolate.splprep([XY[:,0], XY[:,1]], k=2)
                    intX, intY = interpolate.splev(np.linspace(0, 1, 100), tck, der=0)
                    stackXY = np.vstack((intX, intY))
                    
                    X3top = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height())
                    X3bot = (p3.get_x()+p3.get_width()/2,p3.get_y())
                    X3left = (p3.get_x(),p3.get_y()+p3.get_height()/2)
                    X3right = (p3.get_x()+p3.get_width(),p3.get_y()+p3.get_height()/2)
                    
                    n = -1
                    arrthres_v = .02
                    arrthres_h = .02
                    while (((stackXY.T[n][0] > (X3left[0]-arrthres_h)) and (stackXY.T[n][0] < (X3right[0]+arrthres_h))
                        and (stackXY.T[n][1] > (X3bot[1]-arrthres_v)) and (stackXY.T[n][1] < (X3top[1]+arrthres_v)))
                        and (np.abs(n) < np.shape(stackXY)[1] - 10)):
                        n -= 1
                   
                    lpath = Path(stackXY.T[3:n])
                    
                    e = FancyArrowPatch(path=lpath,
                                        arrowstyle='-|>',
                                        mutation_scale=10.0,
                                        lw=(1+self.edgelw),
                                        color=self.reactionColor)
                    ax.add_patch(e)
                    
                    if j[0] in floatingId:
                        if (np.abs(stoch[stoch_row.index(j[0])][i]) > 1):
                            slope = (lpath.vertices[0][1] - lpath.vertices[10][1])/(lpath.vertices[0][0] - lpath.vertices[10][0])
                            x_prime = np.sqrt(0.01/(1 + np.square(slope)))
                            y_prime = -slope*x_prime
                            plt.text(x_prime+lpath.vertices[10][0], y_prime+lpath.vertices[10][1], int(np.abs(stoch[stoch_row.index(j[0])][i])), 
                                     fontsize=self.fontsize, horizontalalignment='center', 
                                     verticalalignment='center', color=self.reactionColor)
                    if j[1] in floatingId:
                        if (np.abs(stoch[stoch_row.index(j[1])][i]) > 1):
                            slope = (lpath.vertices[0][1] - lpath.vertices[-20][1])/(lpath.vertices[0][0] - lpath.vertices[-20][0])
                            x_prime = np.sqrt(0.01/(1 + np.square(slope)))
                            y_prime = -slope*x_prime
                            plt.text(x_prime+lpath.vertices[-20][0], y_prime+lpath.vertices[-20][1], int(np.abs(stoch[stoch_row.index(j[1])][i])), 
                                     fontsize=self.fontsize, horizontalalignment='center', 
                                     verticalalignment='center', color=self.reactionColor)
                    
        # Modifiers
        seen={}
        for i, e in enumerate(mod_flat):
            n1 = G.node[e]['patch']
            n2 = G.node[modtarget_flat[i]]['patch']
            rad = 0.1
            shrinkB = 5.
            
            if (e,modtarget_flat[i]) in seen:
                rad = seen.get((e,modtarget_flat[i])) # TODO: No curvature when there is just a single line between two nodes
                rad = (rad+np.sign(rad)*0.1)*-1 # TODO: Change curvature
                
            X1 = (n1.get_x()+n1.get_width()/2,n1.get_y()+n1.get_height()/2)
            X2 = (n2.get_x()+n2.get_width()/2,n2.get_y()+n2.get_height()/2)
            
            if modtype_flat[i] == 'inhibitor': # inhibition
                color=self.modifierColor
                arrowstyle='-['
                shrinkB = 10.
            else: # activation
                color=self.modifierColor
                arrowstyle='-|>'
            e = FancyArrowPatch(X1,
                                X2,
                                patchA=n1,
                                patchB=n2,
                                shrinkB=shrinkB,
                                arrowstyle=arrowstyle,
                                connectionstyle='arc3,rad=%s'%rad,
                                mutation_scale=10.0,
                                lw=G[e][modtarget_flat[i]]['weight'],
                                color=color)
            seen[(e,modtarget_flat[i])]=rad
            ax.add_patch(e)
            ax.add_patch(n1)
        
        
        # Add reaction nodes at last to put it on top
        if self.drawReactionNode:
            allnodes = speciesId + rid
        else:
            allnodes = speciesId
        
        if 'Input' in G.node:
            allnodes += ['Input']
        if 'Output' in G.node:
            allnodes += ['Output']
        for i in range(len(allnodes)):
            ax.add_patch(G.node[allnodes[i]]['patch'])
        
        # reset width and height
        ax.autoscale()
        fig.set_figwidth((abs(max_width[0] - max_width[1])+0.5)*5)
        fig.set_figheight((abs(max_height[0] - max_height[1])+0.5)*5)
        plt.axis('off')
        plt.axis('equal')
        
        plt.show()
        

class NetworkEnsemble():
    
    def __init__(self, models):
        """
        Creates a new NetworkEnsemble object. 
        
        :param models: list of SBML or Antimony strings of models
        :type name: list
        """
        
        self.rrInstances = []
        
        for m in models:
            try:
                self.rrInstances.append(te.loadSBMLModel(m))
            except:
                try:
                    self.rrInstances.append(te.loadAntimonyModel(m))
                except:
                    raise Exception("Input does not seem to be a valid list of SBML or Antimony string")
                    
        self.reset()
    
    
    def reset(self):
        """
        Resets all properties
        """
    
        self.scale = 1.25
        self.fontsize = 20
        self.edgelw = 10
        self.nodeColor = 'tab:blue'
        self.reactionNodeColor = 'tab:gray'
        self.labelColor = 'w'
        self.labelReactionIds = False
        self.reactionColor = 'k'
        self.modifierColor = 'tab:red'
        self.boundaryColor = 'tab:green'
        self.nodeEdgeColor = 'k'
        self.nodeEdgelw = 0
        self.highlight = []
        self.hlNodeColor = 'tab:purple'
        self.hlNodeEdgeColor = 'tab:pink'
        self.edgeLabel = True
        self.edgeLabelFontSize = 12
        self.drawReactionNode = True
        self.breakBoundary = False
        self.weights = []
        self.edgeTransparency = False
    
    
    def getLayout(self):
        """
        Return the layout
        """
        allRxn = []
        count = []
        rid = []
        mod = []
        mod_target = []
        mod_type = []
        rid_ind = 0
        
        if len(self.weights) > 0:
            if len(self.weights) != len(self.rrInstances):
                raise Exception("The dimension of weights provides does not match "
                                "the number of models given")
    
        for rind, r in enumerate(self.rrInstances):
            rct = []
            prd = []
            mod_m = []
            mod_target_m = []
            kineticLaw = []
            mod_type_m = []
            
            numBnd = r.getNumBoundarySpecies()
            numFlt = r.getNumFloatingSpecies()
            boundaryId = r.getBoundarySpeciesIds()
            floatingId = r.getFloatingSpeciesIds()
            speciesId = boundaryId + floatingId
            rid_temp = r.getReactionIds()
            
            # prepare symbols for sympy
            boundaryId_sympy = [] 
            floatingId_sympy = []
            
            # Fix issues with reserved characters
            for i in range(numBnd):
                if boundaryId[i] == 'S':
                    boundaryId_sympy.append('_S')
                else:
                    boundaryId_sympy.append(boundaryId[i])
            
            for i in range(numFlt):
                if floatingId[i] == 'S':
                    floatingId_sympy.append('_S')
                else:
                    floatingId_sympy.append(floatingId[i])
                    
            paramIdsStr = ' '.join(r.getGlobalParameterIds())
            floatingIdsStr = ' '.join(floatingId_sympy)
            boundaryIdsStr = ' '.join(boundaryId_sympy)
            comparmentIdsStr = ' '.join(r.getCompartmentIds())
            
            allIds = paramIdsStr + ' ' + floatingIdsStr + ' ' + boundaryIdsStr + ' ' + comparmentIdsStr
            
            avsym = sympy.symbols(allIds)
            
            doc = tesbml.readSBMLFromString(r.getSBML())
            sbmlmodel = doc.getModel()
        
            for slr in sbmlmodel.getListOfReactions():
                temprct = []
                tempprd = []
                tempmod = []
                
                sbmlreaction = sbmlmodel.getReaction(slr.getId())
                for sr in range(sbmlreaction.getNumReactants()):
                    sbmlrct = sbmlreaction.getReactant(sr)
                    temprct.append(sbmlrct.getSpecies())
                for sp in range(sbmlreaction.getNumProducts()):
                    sbmlprd = sbmlreaction.getProduct(sp)
                    tempprd.append(sbmlprd.getSpecies())
                for sm in range(sbmlreaction.getNumModifiers()):
                    sbmlmod = sbmlreaction.getModifier(sm)
                    tempmod.append(sbmlmod.getSpecies())
                kl = sbmlreaction.getKineticLaw()
                
                if len(temprct) == 0:
                    rct.append(['Input'])
                else:
                    rct.append(temprct)
                if len(tempprd) == 0:
                    prd.append(['Output'])
                else:
                    prd.append(tempprd)
                mod_m.append(tempmod)
                
                # Update kinetic law according to change in species name
                kl_split = kl.getFormula().split(' ')
                for i in range(len(kl_split)):
                    if kl_split[i] == 'S':
                        kl_split[i] = '_S'
                
                kineticLaw.append(' '.join(kl_split))
            
            # use sympy for analyzing modifiers weSmart
            for ml in range(len(mod_m)):
                mod_type_temp = []
                expression = kineticLaw[ml]
                n,d = sympy.fraction(expression)
                for ml_i in range(len(mod_m[ml])):
                    if n.has(mod_m[ml][ml_i]):
                        mod_type_temp.append('activator')
                    elif d.has(mod_m[ml][ml_i]):
                        mod_type_temp.append('inhibitor')
                    else:
                        continue
                mod_type_m.append(mod_type_temp)
            
            for i in range(len(mod_m)):
                mod_target_temp = []
                if len(mod_m[i]) > 0:
                    mod_target_temp.append(rid_temp[i]) #FIXME: issue with rids
                mod_target_m.append(mod_target_temp)
                
            mod_flat = [item for sublist in mod_m for item in sublist]
            modtype_flat = [item for sublist in mod_type_m for item in sublist]
            modtarget_flat = [item for sublist in mod_target_m for item in sublist]
            
            if self.breakBoundary:
                speciesId = []
                boundaryId_temp = []
                bc = 0
                for i in range(len(rid_temp)):
                    for j in range(len(rct[i])):
                        if rct[i][j] in boundaryId:
                            rct[i][j] = rct[i][j] + '_' + str(bc)
                            speciesId.append(rct[i][j])
                            boundaryId_temp.append(rct[i][j])
                            bc += 1
                    for k in range(len(prd[i])):
                        if prd[i][k] in boundaryId:
                            prd[i][k] = prd[i][k] + '_' + str(bc)
                            speciesId.append(prd[i][k])
                            boundaryId_temp.append(prd[i][k])
                            bc += 1
                for i in range(numFlt):
                    speciesId.append(floatingId[i])
                boundaryId = boundaryId_temp
            
            for t in range(sbmlmodel.getNumReactions()):
                if [rct[t], prd[t]] not in allRxn:
                    allRxn.append([rct[t], prd[t]])
                    if len(self.weights) > 0:
                        count.append(1*self.weights[rind])
                    else:
                        count.append(1)
                    rid.append("J" + str(rid_ind))
                    mod.append(mod_flat)
                    mod_type.append(modtype_flat)
                    mod_target.append(modtarget_flat)
                    rid_ind += 1
                else:
                    if len(self.weights) > 0:
                        count[allRxn.index([rct[t], prd[t]])] += 1*self.weights[rind]
                    else:
                        count[allRxn.index([rct[t], prd[t]])] += 1
                    
        count = np.divide(count, len(self.rrInstances))
    
        # initialize directional graph
        G = nx.DiGraph()
    
        # add edges
        for i in range(len(allRxn)):
            for k in range(len(allRxn[i][0])):
                G.add_edges_from([(allRxn[i][0][k], rid[i])], weight=(count[i]*self.edgelw))
            for j in range(len(allRxn[i][1])):
                G.add_edges_from([(rid[i], allRxn[i][1][j])], weight=(count[i]*self.edgelw))
                        
            if len(mod[i]) > 0:
                if mod_type[i][0] == 'inhibitor':
                    G.add_edges_from([(mod[i][0], rid[i])], weight=(count[i]*self.edgelw))
                elif mod_type[i][0] == 'activator':
                    G.add_edges_from([(mod[i][0], rid[i])], weight=(count[i]*self.edgelw))
    
        # calcutate positions
        thres = 0.1
        shortest_dist = dict(nx.shortest_path_length(G, weight='weight'))
        pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
        
        dist_flag = True
        maxIter = 50
        maxIter_n = 0
        
        while dist_flag and (maxIter_n < maxIter):
            dist_flag = False
            for i in itertools.combinations(speciesId, 2):
                pos_dist = np.linalg.norm(pos[i[0]] - pos[i[1]])
                if pos_dist < thres:
                    dist_flag = True
                    shortest_dist[i[0]][i[1]] = 4
            pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
            maxIter_n += 1
        
        return pos
    
    
    def drawWeightedDiagram(self):
        """     
        Draw weighted reaction network based on frequency of reactions
        
        """
        
        # extract reactant, product, modifiers, and kinetic laws
        allRxn = []
        count = []
        rid = []
        mod = []
        mod_target = []
        mod_type = []
        rid_ind = 0
        
        if len(self.weights) > 0:
            if len(self.weights) != len(self.rrInstances):
                raise Exception("The dimension of weights provides does not match "
                                "the number of models given")
    
        for rind, r in enumerate(self.rrInstances):
            rct = []
            prd = []
            mod_m = []
            mod_target_m = []
            kineticLaw = []
            mod_type_m = []
            
            numBnd = r.getNumBoundarySpecies()
            numFlt = r.getNumFloatingSpecies()
            boundaryId = r.getBoundarySpeciesIds()
            floatingId = r.getFloatingSpeciesIds()
            speciesId = boundaryId + floatingId
            rid_temp = r.getReactionIds()
            
            # prepare symbols for sympy
            boundaryId_sympy = [] 
            floatingId_sympy = []
            
            # Fix issues with reserved characters
            for i in range(numBnd):
                if boundaryId[i] == 'S':
                    boundaryId_sympy.append('_S')
                else:
                    boundaryId_sympy.append(boundaryId[i])
            
            for i in range(numFlt):
                if floatingId[i] == 'S':
                    floatingId_sympy.append('_S')
                else:
                    floatingId_sympy.append(floatingId[i])
                    
            paramIdsStr = ' '.join(r.getGlobalParameterIds())
            floatingIdsStr = ' '.join(floatingId_sympy)
            boundaryIdsStr = ' '.join(boundaryId_sympy)
            comparmentIdsStr = ' '.join(r.getCompartmentIds())
            
            allIds = paramIdsStr + ' ' + floatingIdsStr + ' ' + boundaryIdsStr + ' ' + comparmentIdsStr
            
            avsym = sympy.symbols(allIds)
            
            doc = tesbml.readSBMLFromString(r.getSBML())
            sbmlmodel = doc.getModel()
        
            for slr in sbmlmodel.getListOfReactions():
                temprct = []
                tempprd = []
                tempmod = []
                
                sbmlreaction = sbmlmodel.getReaction(slr.getId())
                for sr in range(sbmlreaction.getNumReactants()):
                    sbmlrct = sbmlreaction.getReactant(sr)
                    temprct.append(sbmlrct.getSpecies())
                for sp in range(sbmlreaction.getNumProducts()):
                    sbmlprd = sbmlreaction.getProduct(sp)
                    tempprd.append(sbmlprd.getSpecies())
                for sm in range(sbmlreaction.getNumModifiers()):
                    sbmlmod = sbmlreaction.getModifier(sm)
                    tempmod.append(sbmlmod.getSpecies())
                kl = sbmlreaction.getKineticLaw()
                
                if len(temprct) == 0:
                    rct.append(['Input'])
                else:
                    rct.append(temprct)
                if len(tempprd) == 0:
                    prd.append(['Output'])
                else:
                    prd.append(tempprd)
                mod_m.append(tempmod)
                
                # Update kinetic law according to change in species name
                kl_split = kl.getFormula().split(' ')
                for i in range(len(kl_split)):
                    if kl_split[i] == 'S':
                        kl_split[i] = '_S'
                
                kineticLaw.append(' '.join(kl_split))
            
            # use sympy for analyzing modifiers weSmart
            for ml in range(len(mod_m)):
                mod_type_temp = []
                expression = kineticLaw[ml]
                n,d = sympy.fraction(expression)
                for ml_i in range(len(mod_m[ml])):
                    if n.has(mod_m[ml][ml_i]):
                        mod_type_temp.append('activator')
                    elif d.has(mod_m[ml][ml_i]):
                        mod_type_temp.append('inhibitor')
                    else:
                        continue
                mod_type_m.append(mod_type_temp)
            
            for i in range(len(mod_m)):
                mod_target_temp = []
                if len(mod_m[i]) > 0:
                    mod_target_temp.append(rid_temp[i]) #FIXME: issue with rids
                mod_target_m.append(mod_target_temp)
                
            mod_flat = [item for sublist in mod_m for item in sublist]
            modtype_flat = [item for sublist in mod_type_m for item in sublist]
            modtarget_flat = [item for sublist in mod_target_m for item in sublist]
            
            if self.breakBoundary:
                speciesId = []
                boundaryId_temp = []
                bc = 0
                for i in range(len(rid_temp)):
                    for j in range(len(rct[i])):
                        if rct[i][j] in boundaryId:
                            rct[i][j] = rct[i][j] + '_' + str(bc)
                            speciesId.append(rct[i][j])
                            boundaryId_temp.append(rct[i][j])
                            bc += 1
                    for k in range(len(prd[i])):
                        if prd[i][k] in boundaryId:
                            prd[i][k] = prd[i][k] + '_' + str(bc)
                            speciesId.append(prd[i][k])
                            boundaryId_temp.append(prd[i][k])
                            bc += 1
                for i in range(numFlt):
                    speciesId.append(floatingId[i])
                boundaryId = boundaryId_temp
            
            for t in range(sbmlmodel.getNumReactions()):
                if [rct[t], prd[t]] not in allRxn:
                    allRxn.append([rct[t], prd[t]])
                    if len(self.weights) > 0:
                        count.append(1*self.weights[rind])
                    else:
                        count.append(1)
                    rid.append("J" + str(rid_ind))
                    mod.append(mod_flat)
                    mod_type.append(modtype_flat)
                    mod_target.append(modtarget_flat)
                    rid_ind += 1
                else:
                    if len(self.weights) > 0:
                        count[allRxn.index([rct[t], prd[t]])] += 1*self.weights[rind]
                    else:
                        count[allRxn.index([rct[t], prd[t]])] += 1
                    
        count = np.divide(count, len(self.rrInstances))
    
        # initialize directional graph
        G = nx.DiGraph()
    
        # add edges
        for i in range(len(allRxn)):
            for k in range(len(allRxn[i][0])):
                G.add_edges_from([(allRxn[i][0][k], rid[i])], weight=(count[i]*self.edgelw))
            for j in range(len(allRxn[i][1])):
                G.add_edges_from([(rid[i], allRxn[i][1][j])], weight=(count[i]*self.edgelw))
                        
            if len(mod[i]) > 0:
                if mod_type[i][0] == 'inhibitor':
                    G.add_edges_from([(mod[i][0], rid[i])], weight=(count[i]*self.edgelw))
                elif mod_type[i][0] == 'activator':
                    G.add_edges_from([(mod[i][0], rid[i])], weight=(count[i]*self.edgelw))
    
        # calcutate positions
        thres = 0.1
        shortest_dist = dict(nx.shortest_path_length(G, weight='weight'))
        pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
        
        dist_flag = True
        maxIter = 50
        maxIter_n = 0
        
        while dist_flag and (maxIter_n < maxIter):
            dist_flag = False
            for i in itertools.combinations(speciesId, 2):
                pos_dist = np.linalg.norm(pos[i[0]] - pos[i[1]])
                if pos_dist < thres:
                    dist_flag = True
                    shortest_dist[i[0]][i[1]] = 4
            pos = nx.kamada_kawai_layout(G, dist=shortest_dist, scale=self.scale)
            maxIter_n += 1
            
        # check the range of x and y positions
        max_width = []
        max_height = []
        for key, value in pos.items():
            max_width.append(value[0])
            max_height.append(value[1])
        
        max_width = [min(max_width), max(max_width)]
        max_height = [min(max_height), max(max_height)]
        
        # initialize figure
        fig = plt.figure()
        ax = plt.gca()
        
        # add nodes to the figure
        for n in G:
            if n in rid:
                rec_width = 0.05
                rec_height = 0.05
                if n in self.highlight:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                        rec_width, 
                                        rec_height,
                                        boxstyle="round,pad=0.01, rounding_size=0.01",
                                        linewidth=self.nodeEdgelw, 
                                        edgecolor=self.hlNodeEdgeColor, 
                                        facecolor=self.hlNodeColor)
                else:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                   rec_width, 
                                   rec_height,
                                   boxstyle="round,pad=0.01, rounding_size=0.01",
                                   linewidth=self.nodeEdgelw, 
                                   edgecolor=self.nodeEdgeColor, 
                                   facecolor=self.reactionNodeColor)
            else:
                # TODO: if the label is too long, increase the height and change line/abbreviate?
                rec_width = max(0.04*(len(n)+2), 0.17)
                rec_height = 0.12
                if (n in boundaryId) or (n == 'Input') or (n == 'Output'):
                    node_color = self.boundaryColor
                else:
                    node_color = self.nodeColor
                if n in self.highlight:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                       rec_width, 
                                       rec_height,
                                       boxstyle="round,pad=0.01, rounding_size=0.02",
                                       linewidth=self.nodeEdgelw, 
                                       edgecolor=self.hlNodeEdgeColor, 
                                       facecolor=self.hlNodeColor)
                else:
                    c = FancyBboxPatch((pos[n][0]-rec_width/2, pos[n][1]-rec_height/2),
                                   rec_width, 
                                   rec_height,
                                   boxstyle="round,pad=0.01, rounding_size=0.02",
                                   linewidth=self.nodeEdgelw, 
                                   edgecolor=self.nodeEdgeColor, 
                                   facecolor=node_color)
                plt.text(pos[n][0], pos[n][1], n, 
                         fontsize=self.fontsize, horizontalalignment='center', 
                         verticalalignment='center', color=self.labelColor)
            G.node[n]['patch'] = c
        
        # add edges to the figure
        for i in range(len(allRxn)):
            for j in [list(zip(x,allRxn[i][1])) for x in itertools.combinations(allRxn[i][0],len(allRxn[i][1]))][0]:
                p1 = G.node[j[0]]['patch']
                p2 = G.node[rid[i]]['patch']
                p3 = G.node[j[1]]['patch']
    
                X1 = (p1.get_x()+p1.get_width()/2,p1.get_y()+p1.get_height()/2)
                X2 = (p2.get_x()+p2.get_width()/2,p2.get_y()+p2.get_height()/2)
                X3 = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height()/2)
                XY = np.vstack((X1, X2, X3))
                
                tck, u = interpolate.splprep([XY[:,0], XY[:,1]], k=2)
                intX, intY = interpolate.splev(np.linspace(0, 1, 100), tck, der=0)
                stackXY = np.vstack((intX, intY))
                
                X3top = (p3.get_x()+p3.get_width()/2,p3.get_y()+p3.get_height())
                X3bot = (p3.get_x()+p3.get_width()/2,p3.get_y())
                X3left = (p3.get_x(),p3.get_y()+p3.get_height()/2)
                X3right = (p3.get_x()+p3.get_width(),p3.get_y()+p3.get_height()/2)
                
                n = -1
                arrthres_v = .02
                arrthres_h = .02
                while ((stackXY.T[n][0] > (X3left[0]-arrthres_h)) and (stackXY.T[n][0] < (X3right[0]+arrthres_h))
                    and (stackXY.T[n][1] > (X3bot[1]-arrthres_v)) and (stackXY.T[n][1] < (X3top[1]+arrthres_v))):
                    n -= 1
               
                lpath = Path(stackXY.T[3:n])
                
                if self.edgeTransparency:
                    alpha = count[i]
                else:
                    alpha = None

                e = FancyArrowPatch(path=lpath,
                                    arrowstyle='-|>',
                                    mutation_scale=10.0,
                                    lw=(count[i]*self.edgelw),
                                    alpha=alpha,
                                    color=self.reactionColor)
                ax.add_patch(e)
                
            # Edge labels
            if self.edgeLabel:
                c = FancyBboxPatch((stackXY.T[50,0]-0.0325, stackXY.T[50,1]+0.005),
                                   0.125, 
                                   0.05,
                                   boxstyle="round,pad=0.01, rounding_size=0.01",
                                   color='w')
                ax.add_patch(c)
                plt.text(stackXY.T[50,0]+0.03, stackXY.T[50,1]+0.03, round(count[i], 3), 
                     fontsize=self.edgeLabelFontSize, horizontalalignment='center', 
                     verticalalignment='center')
                
        # Modifiers
        seen={}
        for (u,v,d) in G.edges(data=True):
            n1 = G.node[u]['patch']
            n2 = G.node[v]['patch']
            rad = 0.1
            shrinkB = 5.
            if (u,v) in seen:
                rad = seen.get((u,v)) # TODO: No curvature when there is just a single line between two nodes
                rad = (rad+np.sign(rad)*0.1)*-1 # TODO: Change curvature
            
            if u not in rid and v in rid and u in mod_flat and v in modtarget_flat: 
                X1 = (n1.get_x()+n1.get_width()/2,n1.get_y()+n1.get_height()/2)
                X2 = (n2.get_x()+n2.get_width()/2,n2.get_y()+n2.get_height()/2)
                uind = [i for i, e in enumerate(mod_flat) if e == u]
                vind = [i for i, e in enumerate(modtarget_flat) if e == v]
                if modtype_flat[list(set(uind).intersection(vind))[0]] == 'inhibitor': # inhibition
                    color=self.modifierColor
                    arrowstyle='-['
                    shrinkB = 10.
                else: # activation
                    color=self.modifierColor
                    arrowstyle='-|>'
                
                if self.edgeTransparency:
                    alpha = count[i]
                else:
                    alpha = None
                
                e = FancyArrowPatch(X1,
                                    X2,
                                    patchA=n1,
                                    patchB=n2,
                                    shrinkB=shrinkB,
                                    arrowstyle=arrowstyle,
                                    connectionstyle='arc3,rad=%s'%rad,
                                    mutation_scale=10.0,
                                    lw=G[u][v]['weight'],
                                    alpha=alpha,
                                    color=color)
                seen[(u,v)]=rad
                ax.add_patch(e)
        
        # Add nodes at last to put it on top
        if self.drawReactionNode:
            allnodes = speciesId + rid
        else:
            allnodes = speciesId
            
        if 'Input' in G.node:
            allnodes += ['Input']
        if 'Output' in G.node:
            allnodes += ['Output']
        for i in range(len(allnodes)):
            ax.add_patch(G.node[allnodes[i]]['patch'])
        
        # reset width and height
        ax.autoscale()
        fig.set_figwidth((abs(max_width[0] - max_width[1])+0.5)*5)
        fig.set_figheight((abs(max_height[0] - max_height[1])+0.5)*5)
        plt.axis('off')
        plt.axis('equal')
        
        plt.show()
        
        return allRxn, count
