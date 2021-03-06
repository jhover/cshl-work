#!/usr/bin/env python
#
# read in starout format file. 
# create Series, rank,
# merge Series to DataFrame
# Do correlation to build matrix. 
# 
#  STAR / Output format. 
# -quantMode GeneCounts 
# -hseq-count -s yes   /  -s reverse
# columns
# geneID       unstranded_counts   1st_stranded  2nd_stranded

# N_unmapped       2674617    2674617    2674617
# N_multimapping   2828822    2828822    2828822
# N_noFeature      5598327    24570638    24512243
# N_ambiguous      3871509    813790    812892
# ENSG00000223972.5    0    0    0
# ENSG00000227232.5    302    159    143
# ENSG00000278267.1    9    7    2
# ENSG00000243485.4    1    1    0
# ENSG00000237613.2    0    0    0
#

import argparse
import logging
import os

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import networkx as nx


class ExpressionNetwork(object):
    
    def __init__(self, exprdataframe, corrthreshold=None):
        self.log = logging.getLogger()
        self.df = exprdataframe.copy() # don't want foreign reference to other object. 
        self.edgelist = None
        self.threshold=corrthreshold
        self.log.debug("copied inbound correlation dataframe")
        np.fill_diagonal(self.df.values, np.nan)
        if self.threshold is not None:
            (xdim, ydim) = self.df.values.shape
            
            for i in range(0,xdim):
                #print('i is %s' % i)
                for j in range(0,ydim):
                    if self.df.values[i,j] < self.threshold:
                        self.df.values[i,j] = 0                
        #    self.df.apply( lambda x: x if x >= corrthreshold else 0 )
        else:
            self.log.info("No threshold, keeping all. ")


    def build_edge_list(self):
        np.fill_diagonal(self.df.values, np.nan)
        self.edgelist = self.df.stack().reset_index()
        self.edgelist.rename(columns={'level_0' : 'from','level_1' : 'to', 0 : 'weight' }, inplace=True)
        self.edgelist['lineweight'] = ( self.edgelist.weight * 10 ) + 1
        #self.edgelist.
        self.log.info("\n%s" % self.edgelist)

    def plot(self):
        G=nx.from_pandas_edgelist(self.edgelist, source='from',target='to', edge_attr=['weight','lineweight'] )
        nx.draw(G, with_labels=True )
        #nx.draw(G, with_labels=True, width='lineweight' )
        plt.show()    


    def __repr__(self):
        s = "%s\n%s" % (self.df ,self.edgelist)
        return s
            



class ExpressionDataset(object):
    
    def __init__(self, filelist = None, fileformat='starcounts'):
        self.log = logging.getLogger()
        self.dslist = []
        self.df = None
        self.cdf = None
        
        if filelist != None:
            self.handlefiles(filelist, fileformat)
            
    def handlefiles(self, filelist, fileformat='starcounts'):
        ## Use Series
        self.log.info("Handling %s files" % len(filelist))
        for f in filelist:
            ds = ExpressionDataset.parsefile2series(f)
            dsr = ds.rank()
            self.log.debug("\n%s" % dsr)
            self.dslist.append(dsr)      
        self.df = pd.concat(self.dslist, axis=1)
        
        # (Re-)do pairwise correlation 
        self.log.info("Performing pair-wise correlation...")
        self.cdf = self.df.corr(method='spearman')
        self.log.debug(self.cdf)


        
        
    def __repr__(self):
        s = "%s\n%s" % (self.df, self.cdf)
        return s


    def plot(self):
        self.log.info("Generating heatmap...")
                
        mask = np.zeros_like(self.cdf)
        mask[np.triu_indices_from(mask)] =True
        
        ax = sns.heatmap( self.cdf,
                          mask=mask,
                          vmin=.3, vmax=.60, 
                          #cmap="Reds_r",
                          center=0,
                          #cmap = sns.color_palette("ch:2.5,-.2,dark=.3"),
                          cmap = sns.color_palette("Blues_d"),
                          #cmap=sns.diverging_palette(20,220,n=200),
                          square=True )
        ax.set_xticklabels(
            ax.get_xticklabels(),
            rotation=45,
            horizontalalignment='right')     
              
        # Adjust to make room for long geneIDs on axes.
        plt.subplots_adjust(left=0.2, bottom=0.2)
        plt.show()

#  https://gist.githubusercontent.com/drazenz/a5f4b7a183a92695328a710681cc780a/raw/9de8272dc5af80c2cd3a120c456fedbfbb1918ed/step_4.py
#
#  Code fragment to adjust how vlues are mapped to colors. This could let us display a full range
#  of colors applied to values from .5 to .9 intead of 0 to 1 . 
#
    @classmethod
    def value_to_color(val):
        n_colors = 256
        palette + sns.diverging_palette(20,220, n = n_colors)
        color_min, color_max = [.50, .90]
        
        val_position = float( ( val - color_min)) / (color_max - color_min)
        ind = int(val_position * (n_colors - 1 ))
        return palett[ind]

    @classmethod
    def parsefile2series(cls, filename):
        logging.debug("Processing file %s" % filename)
        (head, tail) = os.path.split(filename)    
        sname = tail.split('.')[0]
          
        f = open(filename)
        lines = f.readlines()
        data = {}          
        # handle values. 
        for line in lines[4:]:
            (label, unstrand, strand1, strand2) = [ f.strip() for f in line.split('\t') ]
            data[label] = strand2
    
        logging.debug("data length is %s" % len(data))
        ds = pd.Series( data, name=sname )
        logging.debug("\n%s" % ds.head() )  
        return ds    
    

def geteds():
        filelist=['starouts/SRR1470727.ReadsPerGene.out.tab',
                     'starouts/SRR1470774.ReadsPerGene.out.tab',
                     'starouts/SRR1470751.ReadsPerGene.out.tab',
                     'starouts/SRR1470798.ReadsPerGene.out.tab']
        return ExpressionDataset(filelist)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s (UTC) [ %(levelname)s ] %(name)s %(filename)s:%(lineno)d %(funcName)s(): %(message)s')
    
    parser = argparse.ArgumentParser()
      
    parser.add_argument('-d', '--debug', 
                        action="store_true", 
                        dest='debug', 
                        help='debug logging')

    parser.add_argument('-v', '--verbose', 
                        action="store_true", 
                        dest='verbose', 
                        help='verbose logging')

    parser.add_argument('infiles', 
                        metavar='infiles', 
                        type=str, 
                        nargs='+',
                        help='a list of single-cell expression files')
    
    parser.add_argument('-p','--plot',
                        action="store_true",
                        default=False,
                        dest='plot', 
                        help='create coexpression plot')
    
    parser.add_argument('-g','--graph',
                        action="store_true",
                        default=False,
                        dest='graph', 
                        help='create cell-cell network graph ')    
              
    args= parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    filelist = args.infiles 
    logging.info("%d files to process. " % len(filelist))
    
    eds = ExpressionDataset(filelist)
    print(eds)
    
    enw = ExpressionNetwork( eds.cdf, corrthreshold=0.71 )
    enw.build_edge_list()
    
    if args.plot:
        eds.plot()
    else:
        print(eds)
    
    if args.graph:
        enw.plot()
    else:
        print(enw)
          
