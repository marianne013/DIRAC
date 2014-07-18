#!/bin/env python

import re, sys, tempfile, commands, os, urllib

class TorqueBatch( object ):

  def submitJob( self, **kwargs ):
    """ Submit nJobs to the Torque batch system
    """
    
    executable = kwargs.get( 'Executable' )
    if not executable:
      return ( -1, [] )
    outputDir = kwargs.get( 'OutputDir' )
    if not outputDir:
      return ( -1, [] )
    errorDir = kwargs.get( 'ErrorDir' )
    if not errorDir:
      return ( -1, [] )
    queue = kwargs.get( 'Queue' )
    if not queue:
      return ( -1, [] )
    submitOptions = kwargs.get( 'SubmitOptions' )
    if not submitOptions:
      return ( -1, [] )
    nJobs = kwargs.get( 'NJobs' )
    if not nJobs:
      nJobs = 1
    
    jobIDs = []
    status = -1
    for i in range( int(nJobs) ):
      cmd = "qsub -o %s -e %s -q %s -N DIRACPilot %s %s" % ( outputDir,
                                                             errorDir,
                                                             queue,
                                                             submitOptions,
                                                             executable )
      status,output = commands.getstatusoutput(cmd)
      if status == 0:
        jobIDs.append(output)
      else:
        break                                                         
  
    if jobIDs:
      return ( 0, jobIDs )
    else:
      return ( status, [] )
      
def submitJob( executable,outputDir,errorDir,nJobs,jobDir,queue,submitOptions ):
  """ Submit nJobs to the Torque batch system
  """
  jobIDs = []
  for i in range( int(nJobs) ):
    cmd = "qsub -o %s -e %s -q %s -N DIRACPilot %s %s" % ( outputDir,
                                                           errorDir,
                                                           queue,
                                                           submitOptions,
                                                           executable )
    status,output = commands.getstatusoutput(cmd)
    if status == 0:
      jobIDs.append(output)
    else:
      break                                                         

  if jobIDs:
    print 0
    for job in jobIDs:
      print job
  else:
    print status
    print output
    
  return status

def killJob( jobList ):
  """ Kill jobs in the given list
  """
  
  result = 0
  successful = []
  failed = []
  for job in jobList:
    status,output = commands.getstatusoutput( 'qdel %s' % job )
    if status != 0:
      result += 1
      failed.append( job )
    else:
      successful.append( job )  
  
  print result
  for job in successful:
    print job
  return result
  
def getJobStatus( jobList, user ):

  print -1
  return -1
  
def getCEStatus( user ):

  """ Get the overall CE status
  """

  cmd = 'qselect -u %(user)s -s WQ | wc -l; qselect -u %(user)s -s R | wc -l' %{ 'user': user}
  status,output = commands.getstatusoutput( cmd )

  if status != 0:
    print status
    print output
    return status

  waitingJobs, runningJobs = output.split()[:2]

  # Final output
  status = 0
  print status
  print ":::".join( ["Waiting",str(waitingJobs)] )
  print ":::".join( ["Running",str(runningJobs)] )
  return status

#####################################################################################

# Get standard arguments and pass to the interface implementation functions

command = sys.argv[1]
print "============= Start output ==============="
if command == "submit_job":
  executable,outputDir,errorDir,workDir,nJobs,infoDir,jobStamps,queue,submitOptions = sys.argv[2:]
  submitOptions = urllib.unquote(submitOptions)
  if submitOptions == '-':
    submitOptions = ''
  status = submitJob( executable, outputDir, errorDir, nJobs, outputDir, queue, submitOptions )
elif command == "kill_job":
  jobStamps,infoDir = sys.argv[2:]
  jobList = jobStamps.split('#')
  status = killJob( jobList )
elif command == "job_status":
  jobStamps,infoDir,user = sys.argv[2:]
  jobList = jobStamps.split('#')
  status = getJobStatus( jobList, user )  
elif command == "status_info":
  infoDir,workDir,user,queue = sys.argv[2:]
  status = getCEStatus( user )   

sys.exit(status)
