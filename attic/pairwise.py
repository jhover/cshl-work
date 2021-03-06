#!/usr/bin/env python
#
# Process all .fasta files in a directory, producing
# pairwise similarity statistics to an output file
#   
# Needleman-Wunsch global sequence alignment
# Comparing homology/proteins with similar function  in similar-sized 
# sequenes
#
#  time needle -gapopen 10.0 
#              -gapextend 0.5   
#              -asequence 001R_FRG3G.fasta 
#              -bsequence 002L_FRG3G.fasta 
#              -outfile 001R_FRG3Gx002L_FRG3G.water

#
#  Finding conserved domains or motifs. 
#
#  time water -gapopen 10.0 
#             -gapextend 0.5   
#             -asequence 001R_FRG3G.fasta 
#             -bsequence 002L_FRG3G.fasta 
#             -outfile 001R_FRG3Gx002L_FRG3G.water

#
#  Esprit http://www.ijbcb.org/ESPRITPIPE/php/download.php
#  Won tests of PSA tools. ICBR Interdisciplinary Centor for Biotechnology Research
#    University of Florida. 
#  ??
# https://www.majordifferences.com/2016/05/difference-between-global-and-local.html
#
# Total comparisons of N things will be:  N * .5N
# E.g. For a 30-second comparison, we can do ~20000 in 10 hours with 16 cores: 120/hr/core * 16 cores * 10 hrs = 19200
# 20000 comparsions means ~200 items. 200 * 100 = 20000
#
#

import argparse
import logging
import os
import subprocess
import sys
import threading
import time
import traceback

class CommandRunner(threading.Thread):
    
    def __init__(self, overwrite=True, *args, **kwrds):
        super(CommandRunner, self).__init__(*args, **kwrds)
        self.log = logging.getLogger()
        # self.commands is a list of tuples  (commandstr, outfilepath)
        self.commands = []
        self.overwrite = overwrite
        
          
    def run(self):
        for (cmd, of) in self.commands: 
            self.log.info("Running cmd='%s' outfile=%s " % (cmd, of))
            if os.path.exists(of) and not self.overwrite:
                self.log.debug("Outfile %s exists. Skipping..." % of)
            else:
                cp = subprocess.run(cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.log.debug("Ran cmd='%s' returncode=%s " % (cmd, cp.returncode))

            
    def __repr__(self):
        s = ""
        s += "[%s]CommandRunner with %d commands. " % (self.name, len(self.commands))
        return s


class PairwiseRun(object):
    
    def __init__(self, filelist, workdir, overwrite=False, nthreads=1, program='needle' ):
        self.log = logging.getLogger()
        self.filelist = filelist
        self.threadlist = []
        self.overwrite = overwrite
        self.nthreads = int(nthreads)
        self.program = program
        self.workdir = os.path.abspath(os.path.expanduser(workdir))
        if not os.path.exists(self.workdir):
            os.mkdir(self.workdir)
            self.log.info("Created workdir %s" % self.workdir)
        self.log.debug("Created PairwiseRun workdir=%s" % self.workdir)


    def makewatercommand(self, f1, f2):
        #self.log.debug("water: comparing file %s to file %s" % ( f1, f2))
        f1 = os.path.abspath(f1)
        f2 = os.path.abspath(f2)
        
        f1base = os.path.splitext(os.path.basename(f1))[0]
        f2base = os.path.splitext(os.path.basename(f2))[0]
        outfile = "%s/%sx%s.water" % (self.workdir, f1base, f2base)
        #self.log.debug("outfile=%s" % outfile)
        cmdlist = ['time', 'water']
        cmdlist.append( '-gapopen 10.0' )
        cmdlist.append('-gapextend 0.5' )
        cmdlist.append('-asequence %s' % f1 )
        cmdlist.append('-bsequence %s' % f2 )
        cmdlist.append('-outfile %s' % outfile )
        #self.log.debug("cmdlist=%s" % cmdlist)
        cmd = ' '.join(cmdlist).strip()
        #self.log.debug("command is '%s'" % cmd)
        return (cmd, outfile)
        #self.log.info("Running %s against %s" % (f1, f2) )
        #cp = subprocess.run(cmd, check=True, shell=True)
        #self.log.debug("Completed generating %s" % outfile)
        
    
    def makeneedlecommand(self, f1, f2):  
        #self.log.debug("water: comparing file %s to file %s" % ( f1, f2))
        f1 = os.path.abspath(f1)
        f2 = os.path.abspath(f2)
        
        f1base = os.path.splitext(os.path.basename(f1))[0]
        f2base = os.path.splitext(os.path.basename(f2))[0]
        outfile = "%s/%sx%s.needle" % (self.workdir, f1base, f2base)
        #self.log.debug("outfile=%s" % outfile)
        cmdlist = ['time', 'needle']
        cmdlist.append( '-gapopen 10.0' )
        cmdlist.append('-gapextend 0.5' )
        cmdlist.append('-asequence %s' % f1 )
        cmdlist.append('-bsequence %s' % f2 )
        cmdlist.append('-outfile %s' % outfile )
        #self.log.debug("cmdlist=%s" % cmdlist)
        cmd = ' '.join(cmdlist).strip()
        #self.log.debug("command is '%s'" % cmd)
        return (cmd, outfile)

    def makecommands(self):
        #     
        # Take list of files, run water pairwise: 
        #
        commandlist = []
        self.log.info("Beginning to make full pairwise list of commands...")
        listlen = len(self.filelist)
        self.log.info("listlen is %d" % listlen)
        numdone = 0
        for i in range(0,listlen):
            #f1 = os.path.relpath(os.path.expanduser(self.filelist[i]))
            f1 = self.filelist[i]
            for j in range(i + 1,listlen):
                #os.path.relpath(os.path.expanduser(self.filelist[j]))
                f2 = self.filelist[j]
                #self.log.debug("comparing file %s to file %s" % ( f1, f2))
                if self.program == 'needle':
                    c = self.makeneedlecommand(f1, f2)
                elif self.program == 'water':
                    c = self.makewatercommand(f1, f2)
                if numdone % 10000 == 0:
                    self.log.info("Made %d commands so far..." % numdone )
                commandlist.append(c)
                numdone += 1
        self.log.info("Commandlist of %d commands made" % len(commandlist))
        
        for i in range(0,self.nthreads):
            t = CommandRunner(name=str(i), overwrite=self.overwrite)
            self.threadlist.append(t)
        self.log.debug("Made %d Runners to run %d commands" % (len(self.threadlist), len(commandlist)))
        
        for i in range(0, len(commandlist)):           
            touse = i % self.nthreads
            c = commandlist[i]
            usethread = self.threadlist[touse] 
            usethread.commands.append(c)
        
        s = ""
        for t in self.threadlist:
            s+= str(t)
        self.log.debug("%s" % s)

    def runcommands(self):
        self.log.info("Running commands. Starting threads..")
        for t in self.threadlist:
            t.start()

        self.log.info("Running commands. Joining threads..")
        for t in self.threadlist:
            t.join()


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

    parser.add_argument('-i', '--infiles', 
                        dest='infiles', 
                        type=str,
                        required=False, 
                        nargs='+',
                        help='a list of .fasta sequence files')
    
    parser.add_argument('-o', '--overwrite', 
                        action="store_true", 
                        dest='overwrite',
                        default=False, 
                        help='redo commands that have already created output')
    
    parser.add_argument('-w', '--workdir', 
                        action="store", 
                        dest='workdir', 
                        default='~/work/cafa4-play/seqout',
                        help='run-specific workdir [~/work/cafa4-play/seqout]')

    parser.add_argument('-t', '--threads', 
                        action="store", 
                        dest='nthreads', 
                        default=2,
                        help='number of threads to use.')

    parser.add_argument('-L', '--filelist', 
                        action="store", 
                        dest='filelist', 
                        help='file containing listing of files to process (to avoid directory/shell limits)')

    parser.add_argument('-a', '--algorithm', 
                        action="store", 
                        dest='program', 
                        default='needle',
                        help='which EMBOSS algorithm Smith-Waterman (water)|Needleman-Wuensch (needle) [needle]' )    
    
                   
    args= parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    if args.filelist is not None:
        logging.debug("Found filelist opt. ")
        f = open(args.filelist, 'r')
        args.infiles = [x.strip() for x in f]
        f.close()
    
    logging.info("Got arguments...")      
    run = PairwiseRun(args.infiles, args.workdir, args.overwrite, args.nthreads, args.program)
    
    logging.info("Creating commands...")
    run.makecommands()
    
    logging.info("Running commands...")
    run.runcommands()
        