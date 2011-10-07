"""
This module contains a class to synchronize the content of the DataBase with what is the CS
"""

from DIRAC                                           import gLogger, S_OK
from DIRAC.Core.Utilities.SiteCEMapping              import getSiteCEMapping
from DIRAC.Core.Utilities.SiteSEMapping              import getSiteSEMapping
from DIRAC.Core.Utilities.SitesDIRACGOCDBmapping     import getGOCSiteName, getDIRACSiteName

from DIRAC.ResourceStatusSystem.Utilities            import CS, Utils
from DIRAC.Core.LCG.GOCDBClient                      import GOCDBClient

class Synchronizer(object):

#############################################################################

  def __init__( self, rsClient = None, rmDBin = None ):

    self.rsClient    = rsClient
    self.rmDB        = rmDBin
    self.GOCDBClient = GOCDBClient()

    if self.rsClient == None:
      from DIRAC.ResourceStatusSystem.Client.ResourceStatusClient import ResourceStatusClient
      self.rsClient = ResourceStatusClient()

    if self.rmDB == None:
      from DIRAC.ResourceStatusSystem.DB.ResourceManagementDB import ResourceManagementDB
      self.rmDB = ResourceManagementDB()



#############################################################################
  def sync( self, _a, _b ):
    """
    :params:
      :attr:`thingsToSync`: list of things to sync
    """

    # FIXME: VOBOX not generic
    # FIXME: Add DIRACSites
    # FIXME: Add CONDDB

    thingsToSync = [ 'Sites', 'VOBOX', 'Resources', 'StorageElements', 'RegistryUsers' ]
    gLogger.info( "!!! Sync DB content with CS content for %s !!!" % ( ", ".join(thingsToSync) ) )

    for thing in thingsToSync:
      getattr( self, '_sync' + thing )()

    return S_OK()

#############################################################################

  def _syncSites( self ):
    """
    Sync DB content with sites that are in the CS
    """
    def getGOCTier(sitesList):
      return "T" + str(min([int(v) for v in Utils.unpack(CS.getSiteTier(sitesList))]))

    # sites in the DB now
    sitesDB = Utils.unpack(self.rsClient.getSites())
    sitesDB = [s[0] for s in sitesDB]

    # sites in CS now
    sitesCS = Utils.unpack(CS.getSites())

    # remove sites from the DB that are not in the CS
    sitesToDelete = set(sitesDB) - set(sitesCS)
    for s in sitesToDelete:
      self.rsClient.deleteSites(s)

    # add to DB what is missing
    for site in set(sitesCS) - set(sitesDB):
      # DIRAC Tier
      tier = "T" + str(Utils.unpack(CS.getSiteTier( site )))

      # Grid Name of the site
      gridSiteName = Utils.unpack(getGOCSiteName(site))

      # Grid Tier (with a workaround!)
      DIRACSitesOfGridSites = Utils.unpack(getDIRACSiteName(gridSiteName))
      if len( DIRACSitesOfGridSites ) == 1:
        gt = tier
      else:
        gt = getGOCTier( DIRACSitesOfGridSites )

      self.rsClient.addOrModifyGridSite( gridSiteName, gt )
      self.rsClient.addOrModifySite( site, tier, gridSiteName )
      sitesDB.append( site )

#############################################################################

  def _syncVOBOX( self ):
    """
    Sync DB content with VOBoxes
    LHCb specific
    """

    # services in the DB now
    #servicesInDB = self.rsClient.getMonitoredsList( 'Service', paramsList = ['ServiceName'] )
    kwargs = { 'columns' : [ 'ServiceName' ]}
    servicesInDB = self.rsClient.getServicesPresent( **kwargs )#paramsList = ['ServiceName'] )
    servicesInDB = [ s[0] for s in servicesInDB ]

    for site in ['LCG.CNAF.it', 'LCG.IN2P3.fr', 'LCG.PIC.es',
                 'LCG.RAL.uk', 'LCG.GRIDKA.de', 'LCG.NIKHEF.nl']:

      service = 'VO-BOX@' + site
      if service not in servicesInDB:
        self.rsClient.addOrModifyService( service, 'VO-BOX', site )

#############################################################################
# _syncResources HELPER functions

  def __updateService(self, site, type_, servicesInCS, servicesInDB):
    service = type_ + '@' + site
    if service not in servicesInCS:
      servicesInCS.append( service )
    if service not in servicesInDB:
      self.rsClient.addOrModifyService( service, type_, site )
      servicesInDB.append( service )

  def __syncNode(self, NodeInCS, servicesInCS, servicesInDB, resourcesInDB, resourceType, serviceType):
    for node in NodeInCS:
      siteInGOCDB = Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', node ))
      if siteInGOCDB == []:
        siteInGOCDB = Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', Utils.canonicalURL(node) ))
      try:
        siteInGOCDB = siteInGOCDB[0]['SITENAME']
      except IndexError:
        continue
      sites = Utils.unpack(getDIRACSiteName( siteInGOCDB ))
      for site in sites:
        self.__updateService(site, serviceType, servicesInCS, servicesInDB)

      if node not in resourcesInDB and node is not None:
        self.rsClient.addOrModifyResource( node, resourceType, serviceType, 'NULL', siteInGOCDB )
        resourcesInDB.append( node )
############################################################################

  def _syncResources( self ):
    gLogger.info("Starting sync of Resources")

    # resources in the DB now
    #resourcesInDB = self.rsClient.getMonitoredsList( 'Resource', paramsList = ['ResourceName'] )
    kwargs = { 'columns' : [ 'ResourceName' ]}
    resourcesInDB = self.rsClient.getResourcesPresent( **kwargs )#paramsList = ['ServiceName'] )
    resourcesInDB = [r[0] for r in resourcesInDB]

    # services in the DB now
    kwargs = { 'columns' : [ 'ServiceName' ]}
    servicesInDB = self.rsClient.getServicesPresent( **kwargs )#paramsList = ['ServiceName'] )
    #servicesInDB = self.rsClient.getMonitoredsList( 'Service', paramsList = ['ServiceName'] )
    servicesInDB = [s[0] for s in servicesInDB]

    # Site-CE mapping in CS now
    siteCE = Utils.unpack(getSiteCEMapping( 'LCG' ))
    # Site-SE mapping in CS now
    siteSE = Utils.unpack(getSiteSEMapping( 'LCG' ))

    # CEs in CS now
    # http://stackoverflow.com/questions/952914/making-a-flat-list-out-of-list-of-lists-in-python
    CEInCS = [CE for celist in siteCE.values() for CE in celist] # [[a], [b]] -> [a, b], super fast

    # SEs in CS now
    SEInCS = [SE for selist in siteSE.values() for SE in selist]

    # SE Nodes in CS now
    SENodeInCS = [Utils.unpack(CS.getSENodes( SE )) for SE in SEInCS]
    SENodeInCS = [n for n in SENodeInCS if n]                # Filter out None results
    SENodeInCS = list(set(SENodeInCS))                       # Filter out doublons

    # LFC Nodes in CS now
    # FIXME: Refactor.
    LFCNodeInCS_L = []
    LFCNodeInCS_C = []
    for site in Utils.unpack(CS.getLFCSites()):
      for readable in ( 'ReadOnly', 'ReadWrite' ):
        LFCNode = Utils.unpack(CS.getLFCNode( site, readable ))
        if LFCNode is None or LFCNode == []:
          continue
        LFCNode = LFCNode[0]
        if readable == 'ReadWrite':
          if LFCNode not in LFCNodeInCS_C:
            LFCNodeInCS_C.append( LFCNode )
        elif readable == 'ReadOnly':
          if LFCNode not in LFCNodeInCS_L:
            LFCNodeInCS_L.append( LFCNode )

    # FTS Nodes in CS now
    FTSNodeInCS = Utils.unpack(CS.getFTSSites())
    FTSNodeInCS = [Utils.unpack(CS.getFTSEndpoint(site)) for site in FTSNodeInCS]
    FTSNodeInCS = [e for e in FTSNodeInCS if e]
    FTSNodeInCS = [e[0] for e in FTSNodeInCS]

    # VOMS Nodes in CS now
    VOMSNodeInCS = Utils.unpack(CS.getVOMSEndpoints())

    # complete list of resources in CS now
    resourcesInCS = CEInCS + SENodeInCS + LFCNodeInCS_L + LFCNodeInCS_C + FTSNodeInCS + VOMSNodeInCS

    # list of services in CS now (to be done)
    servicesInCS = []

    #remove resources no more in the CS
    for res in set(resourcesInDB) - set(resourcesInCS):
      self.rsClient.deleteResources( res )
      kwargs = { 'columns' : [ 'StorageElementName' ] }
      sesToBeDel = self.rsClient.getStorageElementsPresent( resourceName = res, **kwargs )
     #sesToBeDel = self.rsClient.getMonitoredsList( 'StorageElement', ['StorageElementName'], resourceName = res )
      if sesToBeDel[ 'OK' ]:
        for seToBeDel in sesToBeDel[ 'Value' ]:
          self.rsClient.deleteStorageElements( seToBeDel[ 0 ] )

    # add to DB what is in CS now and wasn't before

    # CEs
    # CEs = Utils.list_flatten(siteCE.values())
    # CEs = [ce for ce in CEs if ce]
    # siteInGOCDB = [Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', ce )) for ce in CEs]
    # siteInGOCDB = [Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', Utils.canonicalURL(ce) ))
    #                for ce in CEs if ce == []]
    # siteInGOCDB = [s for s in siteInGOCDB if len(s) > 0]
    # siteInGOCDB = [siteInGOCDB[0]['SITENAME'] for s in siteInGOCDB]


    # Add CSe to Services/Resources on DB ####################
    gLogger.info("Syncing CEs")
    for site in siteCE.keys():
      if site == 'LCG.Dummy.ch':
        continue
      for ce in siteCE[site]:
        if ce is None:
          continue
        siteInGOCDB = Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', ce ))
        if siteInGOCDB == []:
          siteInGOCDB = Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', Utils.canonicalURL(ce) ))
        try:
          siteInGOCDB = siteInGOCDB[0]['SITENAME']
        except IndexError:
          continue
        self.__updateService(site, "Computing", servicesInCS, servicesInDB)

        if ce not in resourcesInDB:
          CEType = Utils.unpack(CS.getCEType( site, ce ))
          ceType = 'CE'
          if CEType == 'CREAM':
            ceType = 'CREAMCE'
          self.rsClient.addOrModifyResource( ce, ceType, "Computing", site, siteInGOCDB )
          resourcesInDB.append( ce )


    # Add SRMs to Services on DB #################
    gLogger.info("Syncing SRMs")
    siteInGOCDB = [Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', srm ))
                   for srm in SENodeInCS]
    siteInGOCDB = [Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', Utils.canonicalURL(srm) ))
                   for srm in siteInGOCDB if srm == []]
    siteInGOCDB = [s for s in siteInGOCDB if len(s) > 0]
    siteInGOCDB = [s[0]['SITENAME'] for s in siteInGOCDB]
    sites       = [Utils.unpack(getDIRACSiteName( s )) for s in siteInGOCDB]
    for site in sites:
      self.__updateService(site, 'Storage', servicesInCS, servicesInDB)

    # Add SRM to Resources on DB #################
    def addSRMTODB(srm, resourcesInDB):
      if srm and srm not in resourcesInDB:
        self.rsClient.addOrModifyResource( srm, 'SE', "Storage", 'NULL', siteInGOCDB )
        resourcesInDB.append( srm )
    _ = [addSRMTODB(srm, resourcesInDB) for srm in SENodeInCS]

    # LFC_C
    self.__syncNode(LFCNodeInCS_C, servicesInCS, servicesInDB, resourcesInDB, "LFC_C", "Storage")

    # LFC_L
    self.__syncNode(LFCNodeInCS_L, servicesInCS, servicesInDB, resourcesInDB, "LFC_L", "Storage")

    # FTSs
    self.__syncNode(FTSNodeInCS, servicesInCS, servicesInDB, resourcesInDB, "FTS", "Storage")

    # VOMSs
    self.__syncNode(VOMSNodeInCS, servicesInCS, servicesInDB, resourcesInDB, "VOMS", "VOMS")

    #remove services no more in the CS
    for ser in set(servicesInDB) - set(servicesInCS):
      serType = ser.split( '@' )[0]
      if serType != 'VO-BOX':
        self.rsClient.deleteServices( ser )
          #resToBeDel = self.rsClient.getMonitoredsList('Resource', ['ResourceName'], serviceName = ser )
          #if resToBeDel[ 'OK' ]:
          #  for reToBeDel in resToBeDel[ 'Value' ]:
          #    self.rsClient.deleteResources( reToBeDel[ 0 ] )
        try:
          site = ser.split( '@' )[1]
        except:
          print ( ser,site )

        if serType == 'Storage':
          kwargs = { 'columns' : [ 'StorageElementName' ] }
          sesToBeDel = self.rsClient.getStorageElementsPresent( gridSiteName = site, **kwargs )
            #sesToBeDel = self.rsClient.getMonitoredsList('StorageElement', ['StorageElementName'], gridSiteName = site )
          if sesToBeDel[ 'OK' ]:
            for seToBeDel in sesToBeDel[ 'Value' ]:
              self.rsClient.deleteStorageElements( seToBeDel )


#############################################################################

  def _syncStorageElements( self ):

    # Get StorageElements from the CS
    CSSEs = Utils.unpack(CS.getStorageElements())

    kwargs = { 'columns' : [ 'StorageElementName' ] }
    DBSEs = self.rsClient.getStorageElementsPresent( **kwargs )
    #DBSEs = self.rsClient.getMonitoredsList( 'StorageElement',
    #                                                   paramsList = [ 'StorageElementName' ] )
    try:
      DBSEs = [ x[ 0 ] for x in DBSEs ]
    except IndexError:
      pass

    # Remove storageElements that are in DB but not in CS
    for se in set(DBSEs) - set(CSSEs):
      #self.rsClient.removeStorageElement( storageElementName = se, resourceName = None )
      self.rsClient.deleteStorageElements( se )

    # Add new storage Elements
    for SE in CSSEs:
      srm = Utils.unpack(CS.getSENodes( SE ))
      if srm == None:
        continue
      siteInGOCDB = Utils.unpack(self.GOCDBClient.getServiceEndpointInfo( 'hostname', srm ))
      if siteInGOCDB == []: continue
      siteInGOCDB = siteInGOCDB[ 0 ][ 'SITENAME' ]

      if SE not in DBSEs:
        self.rsClient.addOrModifyStorageElement( SE, srm, siteInGOCDB )
        DBSEs.append( SE )

#############################################################################

  def _syncRegistryUsers(self):
    users = CS.getTypedDictRootedAt("Users", root= "/Registry")
    for u in users:
      if type(users[u]['DN']) == list:
        users[u]['DN'] = users[u]['DN'][0]
      if type(users[u]['Email']) == list:
        users[u]['Email'] = users[u]['Email'][0]

      users[u]['DN'] = users[u]['DN'].split('=')[-1]
      self.rmDB.registryAddUser(u, users[u]['DN'].lower(), users[u]['Email'].lower())
