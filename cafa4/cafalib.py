#!/usr/bin/env python
#
#     Top level  Runplugins      Infoplugins
#     CAFA4Run
#                PhmmerPlugin                         
#                OrthologPlugin                       looks up ortholog info
#                                QuickGOPlugin        gets GO info
#                                UniprotGOPlugin      gets GO info
#                Expression
#
# 
#      ************************CANONICAL DATAFRAME COLUMNS*********************************
#   
# COLUMN        DESCRIPTION               MAPPINGS                             EXAMPLES
# cafaid        cafa4 target identifier   N/A                                  T2870000001
# proteinid     UniProtKB:entry/accession  quickgo:gene product_id             P63103
# protein       all caps name                                                  1433B
# gene          Free-text gene name.                                           Lrrk2  Ywahb
# geneid        Gene name+species.                                             LRRK2_MOUSE     
# taxon_id      NCBI taxon id                                                  9606                 
# species       all caps code                                                  MOUSE   PONAB
# goterm        annotated term                                                 GO:0005634
# goaspect      biological process|molecular function|cellular component       cp    bp
# goevicence    evidence codes for GO annotation.                              IEA 
# evalue        BLAST/HMMER/PHMMER expect statistic                                               1.000000e-126
# bias          Adjustement to score for char prevalence                       3.5
# score         BLAST/HMMER/PHMMER bit-score                                   400.3
# db            






__author__ = "John Hover"
__copyright__ = "2019 John Hover"
__credits__ = []
__license__ = "Apache 2.0"
__version__ = "0.99"
__maintainer__ = "John Hover"
__email__ = "hover@cshl.edu"
__status__ = "Testing"

import argparse
from configparser import ConfigParser
import logging
import os
import sys
import tempfile

import pandas as pd
import pdpipe as pdp
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import subprocess

gitpath=os.path.expanduser("~/git/cshl-work/cafa4")
sys.path.append(gitpath)
import ontology
import quickgo
import uniprot

class CAFA4Run(object):
    
    def __init__(self, config, targetlist):
        '''
        Embodies all the processing for a single run against all targets.
        Overall input is a set of Target sequence files. 
        Overall output is a properly-formatted CAFA4 prediction file.   
        
        '''
        self.config = config
        self.targetlist = targetlist
        self.log = logging.getLogger()
        self.outdir = os.path.expanduser( config.get('global','outdir') )
        self.author = config.get('global','author')
        self.modelnumber = config.get('global','modelnumber')
        self.keywords = config.get('global','keywords')
        self.profile = config.get('global','profile')
        self.pipeline = [ x.strip() for x in config.get( self.profile,'pipeline').split(',')]
        self.outbase = config.get( self.profile,'outbase')
    
    def __repr__(self):
        s = "CAFA4Run:"
        for atr in ['outdir','targetlist','pipeline']:
            s += " %s=%s" % (atr, self.__getattribute__(atr))
        return s


    def _cafafile(self, ):
        '''
        E.g. filename:    gillislab_1_10090_go.txt
                          gillislab_1_78_go.txt   
        
        HOVER          GILLIS_LAB
        MODEL          1
        KEYWORDS       orthologs, phmmer
        ACCURACY       1  PR=0.86; RC=0.30
        T100900000001  GO:0042203
        T100900000002  GO:0003998
        .
        .
        .
        
        '''
        pass
    
    

    def execute(self):
        self.log.info("Begin run...")
        
        phm = PhmmerPlugin(self.config, self.targetlist)
        self.log.debug(phm)
        df = phm.execute()
        
        self.log.info("\n%s" % str(df))
        df.to_csv("%s/%s-phmmer.csv" % (self.outdir, self.outbase))
        
        ortho = OrthologPlugin(self.config)
        self.log.debug(ortho)
        df = ortho.execute(df)
        self.log.info("\n%s" % str(df))
        df.to_csv("%s/%s-ortho.csv" % (self.outdir, self.outbase))
        
        
        # not needed if we use quickgo. contains both evidence codes and go_aspect
        #go = GOPlugin(self.config)
        #df = go.execute(df)
        #self.log.info("\n%s" % str(df))
                  
        #self.cafafile("%s/.csv" % (self.outdir, self.outbase)
        
        self.log.info("Ending run...")


class PhmmerPlugin(object):
    '''
    Pipeline object. Takes list of Fasta files to run on, returns pandas dataframe of 
    similar sequences with score. 
    Input:   List of FASTA files 
    Output:  Pandas DataFrame
    '''

    def __init__(self, config, targetlist):
        self.log = logging.getLogger()
        self.config = config
        self.targetlist = targetlist
        self.outdir = os.path.expanduser( config.get('global','outdir') )
        self.database = os.path.expanduser( config.get('phmmer','database') )
        self.score_threshold = config.get('phmmer','score_threshold')
        self.cpus = config.get('phmmer','cpus')
    
    def __repr__(self):
        s = "Phmmer:"
        for atr in ['targetlist','database', 'score_threshold','cpus']:
            s += " %s=%s" % (atr, self.__getattribute__(atr))
        return s        
    
    def execute(self):
        outlist = self.run_phmmer_files(self.targetlist, self.database)
        self.log.debug("phmmer outlist=%s" % outlist)
        outdfs = []
        for outfile in outlist:
            df = self.read_phmmer_table(outfile)
            outdfs.append(df)
        self.log.debug("dflist is %s" % outdfs)
        df = pd.concat(outdfs, ignore_index=True)
        self.log.debug(str(df))
        return df
            
    
    def run_phmmer_files(self, targetlist, database="/data/hover/data/uniprot/uniprot_sprot.fasta"):
    #
    #  time phmmer --tblout 7955.phmmer.2.txt 
    #              --cpu 16 
    #              --noali 
    #              ~/data/cafa4/TargetFiles/sp_species.7955.tfa 
    #              ~/data/uniprot/uniprot_sprot.fasta 
    #              > 7955.phmmer.console.out 2>&1
        
        dbase = database
        outlist = []
        for file in targetlist:
            if not os.path.exists(file):
                raise FileNotFoundError()
            (cmd, outfile) = self._make_phmmer_cmdline(file)
            self.log.debug("Running cmd='%s' outfile=%s " % (cmd, outfile))
            cp = subprocess.run(cmd, 
                                shell=True, 
                                universal_newlines=True, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
            
            outlist.append(outfile)
            self.log.debug("Ran cmd='%s' outfile=%s returncode=%s " % (cmd,outfile, cp.returncode))
        return outlist
            
    def _make_phmmer_cmdline(self, filename):
        outpath = os.path.dirname(filename)
        filebase = os.path.splitext(os.path.basename(filename))[0]
        outfile = "%s/%s.phmmer.tbl.txt" % (self.outdir, filebase)
        #self.log.debug("outfile=%s" % outfile)
        cmdlist = ['time', 'phmmer']
        cmdlist.append( '--tblout  %s ' % outfile )
        cmdlist.append('--noali' )
        cmdlist.append('--cpu %s ' % self.cpus)
        if self.score_threshold is not None:
            cmdlist.append("-T %s " % self.score_threshold)
        cmdlist.append(' %s ' % filename )
        cmdlist.append(' %s ' % self.database )
        cmd = ' '.join(cmdlist).strip()
        #self.log.debug("command is '%s'" % cmd)
        return (cmd, outfile)

    def read_phmmer_table(self, filename):
        self.log.debug("Reading %s" % filename)
        df = pd.read_table(filename, 
                         names=['target','t-acc','cafaid','q-acc',
                                'evalue', 'score', 'bias', 'e-value-dom','score-dom', 'bias-dom', 
                                'exp', 'reg', 'clu',  'ov', 'env', 'dom', 'rep', 'inc', 'description'],
                         skip_blank_lines=True,
                         comment='#',
                         index_col=False,
                         skiprows=3,
                         engine='python', 
                         sep='\s+')
        self.log.debug(str(df))
        self.log.debug("Dropping unneeded columns..")
        df = df.drop(['t-acc', 'q-acc','e-value-dom','score-dom', 'bias-dom', 'exp', 
                 'reg', 'clu',  'ov', 'env', 'dom', 'rep', 'inc', 
                 'description'] , axis=1)
        self.log.debug("Parsing compound fields to define new columns...")
        self.log.debug("Splitting first field for db")
        df['db'] = df.apply(lambda row: row.target.split('|')[0], axis=1)
        self.log.debug("Splitting first field for target accession")
        df['proteinid'] = df.apply(lambda row: row.target.split('|')[1], axis=1)
        self.log.debug("Splitting first field for prot_species")
        df['prot_spec'] = df.apply(lambda row: row.target.split('|')[2], axis=1)
        self.log.debug("Splitting protein_species to set protein")
        df['protein'] =   df.apply(lambda row: row.prot_spec.split('_')[0], axis=1)
        self.log.debug("Splitting protein_species to set species")
        df['species'] =   df.apply(lambda row: row.prot_spec.split('_')[1], axis=1)
        self.log.debug("Dropping split columns...")
        df.drop(columns=['target','prot_spec'], axis=1, inplace=True)
        return df
    

class OrthologPlugin(object):
    '''
    Pipeline object. Takes Pandas dataframe, looks up orthologs and GO codes.  
    Input:  Pandas DataFrame
    Output: Pandas DataFrame
    '''

    def __init__(self, config):
        '''
        
        '''
        self.log = logging.getLogger()
        self.config = config
        self.outdir = os.path.expanduser( config.get('global','outdir') )
        self.backend = config.get('ortholog','backend').strip()
        self.exc_ec_list = [i.strip() for i in config.get('ortholog','excluded_evidence_codes').split(',')] 
        self.uniprot = uniprot.UniProtGOPlugin(self.config)
        self.quickgo = quickgo.QuickGOPlugin(self.config)


    def __repr__(self):
        s = "Orthologs: uniprot"
        for atr in ['outdir','backend']:
            s += " %s=%s" % (atr, self.__getattribute__(atr))
        return s            

        
    def execute(self, dataframe):
        '''
        for each row of dataframe, look up ortholog in uniprot and for each GO code
        add a new row with gene, goterm, gocategory
        
        iterate input df fully, putting new info in new df. 
        merge old + new df, return resulting dataframe
        
        '''
        self.log.info("Looking up each ortholog")

        newdf = None
        
        if self.backend == 'uniprot': 
            self.log.debug("Calling uniprot back end.")
            newdf = self.uniprot.get_df(dataframe)
            
        if self.backend == 'quickgo':
            self.log.debug("Querying QuickGo for %d unique entries" % len(entries))
            udf = self.quickgo.get_df(entries)
            self.log.debug(qdf)
            qdf.to_csv("%s/quickgo.csv" % self.outdir)
        
        self.log.debug("\n%s" % str(newdf))
        return newdf
            
    


class GOPlugin(object):
    '''
    Pipeline object. Takes Pandas dataframe, looks up GO namespace [and evidence codes] by GO term. 
    Input:  Pandas DataFrame
    Output: Pandas DataFrame
    '''

    def __init__(self, config):
        '''
        
        '''
        self.log = logging.getLogger()
        self.config = config
        self.outdir = os.path.expanduser( config.get('global','outdir') )
        self.go = ontology.GeneOntologyGOInfoPlugin()


    def __repr__(self):
        s = "GO:"
        for atr in ['outdir']:
            s += " %s=%s" % (atr, self.__getattribute__(atr))
        return s 

    def execute(self, dataframe):
        gdf = self.go.get_df()
        self.log.debug("\n%a" % str(gdf))
        igdf = gdf.set_index('goterm')
        gdict = igdf.to_dict('index')
        # now indexed by goterm   gdict[goterm] -> {'name': 'osteoblast differentiation', 'namespace': 'bp'}
        # rd['GO:0001649']['namespace']  
                
        dataframe['namespace'] = dataframe.apply(
            lambda row: gdict[row.goterm]['namespace'], 
            axis=1)
        self.log.debug(str(dataframe))
        return dataframe
        



        
        
        
        



#def get_plugin(klassname):
#    return getattr(sys.modules[__name__], klassname)
   
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
                        help='a list of .fasta sequence files')
    
    parser.add_argument('-c', '--config', 
                        action="store", 
                        dest='conffile', 
                        default='~/etc/cafa4.conf',
                        help='Config file path [~/etc/cafa4.conf]')





                    
    args= parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    cp = ConfigParser()
    cp.read(args.conffile)
           
    c4run = CAFA4Run(cp, args.infiles)
    logging.debug(c4run)
    c4run.execute()
