from abaqus import *
from abaqusConstants import *
from AbaqusFiles.ModelModule import MyModel
import numpy as np 
import copy
import regionToolset

class PropertyModule(MyModel):

    def __init__(self,materialName):
        self._modelName=MyModel._modelName
        self._path=MyModel._path
        self._materialName=materialName
        

    def setBasicInfo(self,elasticModules,possionRatio,density):

        loadPath='Constitution/'+str(self._path)
        ElasticData=np.loadtxt(loadPath+'/'+self._materialName+'Elastic.txt')
        #E_SF=np.loadtxt(loadPath+'/'+self._materialName+'ElasticScaleFactor.txt')
        E_SF=np.ones(1000)
        SampleSize=len(E_SF)
        randomPick=np.random.randint(0,SampleSize,SampleSize)

        for i in range(len(ElasticData)):

            materialName=self._materialName+'-'+str(i)
            random=randomPick[i]

            mdb.models[self._modelName].Material(name=materialName)
            thisMaterial=mdb.models[self._modelName].materials[materialName]
            thisMaterial.Elastic(table=((float(elasticModules*E_SF[random]), float(possionRatio)), ))
            thisMaterial.Density(table=((density, ), ))

            self._sectionCreate(materialName)

        if self._materialName=='Matrix':
            self._setCDPInfo()
        elif self._materialName=='Interface':
            self._setCDPInfo()
        

    def _sectionCreate(self,materialName):
        mdb.models[self._modelName].HomogeneousSolidSection(name='SecOf-'+str(materialName), 
            material=materialName, thickness=None)


    def _setCDPInfo(self):

        loadPath='Constitution/'+str(self._path)
        Compress=np.loadtxt(loadPath+'/Compression.txt')
        Tensile=np.loadtxt(loadPath+'/Tension.txt')
        TensionDamage=np.loadtxt(loadPath+'/TensionDamage.txt')
        CompressionDamage=np.loadtxt(loadPath+'/CompressionDamage.txt')

        CDP_SF=np.loadtxt(loadPath+'/'+self._materialName+'CDPScaleFactor.txt')
        SampleSize=len(CDP_SF)
        randomPick=np.random.randint(0,SampleSize,SampleSize)
        for i in range(SampleSize):
            
            materialName=self._materialName+'-'+str(i)
            thisMaterial=mdb.models[self._modelName].materials[materialName]
            thisMaterial.ConcreteDamagedPlasticity(table=((
            38.0, 0.1, 1.16, 0.667, 0.0), ))

            random=randomPick[i]

            Temp_Compress=copy.deepcopy(Compress)
            Temp_Tensile=copy.deepcopy(Tensile)
            Temp_TensionDamage=copy.deepcopy(TensionDamage)
            Temp_CompressionDamage=copy.deepcopy(CompressionDamage)

            Temp_Compress=Compress*CDP_SF[random]
            Temp_Tensile=Tensile*CDP_SF[random]

            Temp_TensionDamage[:,1]=TensionDamage[:,1]*CDP_SF[random]
            Temp_CompressionDamage[:,1]=CompressionDamage[:,1]*CDP_SF[random]
            
            thisMaterial.concreteDamagedPlasticity.ConcreteCompressionHardening(
            table=(Temp_Compress))
            thisMaterial.concreteDamagedPlasticity.ConcreteTensionStiffening(
            table=(Temp_Tensile),type=STRAIN)
            thisMaterial.concreteDamagedPlasticity.ConcreteTensionDamage(
            table=Temp_TensionDamage, type=STRAIN) 
            thisMaterial.concreteDamagedPlasticity.ConcreteCompressionDamage(
            table=Temp_CompressionDamage) 


    def _cal(self,crackStrain,Stress,damageFactor,elasticScaleFactor=1):
        return crackStrain-(damageFactor/(1-damageFactor))*(Stress/(23000*elasticScaleFactor))

def positionDetermine(x,y,z,xcentroid,ycentroid,zcentroid,radi):
    xdistance=abs(x-xcentroid)
    ydistance=abs(y-ycentroid)
    zdistance=abs(z-zcentroid)
    distance=np.sqrt(xdistance**2+ydistance**2+zdistance**2)
    thickness=0.1*radi
    if distance>radi:
        return 'OutSide'
    elif distance<radi and distance>radi-thickness:
        return 'OnBorder'
    else:
        return 'InSide'


def positionResult(xmean,ymean,zmean,sphereData=[]):
    insider,outsider,border=0,0,0
    sphereNum=len(sphereData)
    for sphere in sphereData:
        result=positionDetermine(xmean,ymean,zmean,sphere[0],sphere[1],sphere[2],sphere[3])
        if result=='InSide':
            insider+=1
        elif result=='OutSide':
            outsider+=1
        else:
            border+=1
    if insider>=1:
        return 'Aggregate'
    elif border>=1:
        return 'Interface'
    elif outsider==sphereNum:
        return 'Matrix'


def sectionAssign():
    modelName=MyModel._modelName
    path=MyModel._path
    partName='MeshPart'

    sphereData=[]
    sphereData=np.loadtxt('ModelInfoFiles/'+str(path)+'/sphereData.txt')# 0 1 2 3=x y z r
    p = mdb.models[modelName].parts[partName]
    elements=p.elements
    eleNum=len(elements)
    MatrixSet=[]
    InterfaceSet=[]
    AggregateSet=[]
    # #the first step, determine the node positions
    # nodes=p.nodes
    # nodePosition=[]
    # for i in range(len(nodes)):
    #     x_coordinate=nodes[i][0]
    #     y_coordinate=nodes[i][1]
    #     z_coordinate=nodes[i][2]
    #     result=positionResult(x_coordinate,y_coordinate,z_coordinate,sphereData)
    #     nodePosition.append([i,result])
    # #got the node NO and its position results
    
    #the following program, is to determine the element position by the node number.
    for i in range(eleNum):
        nodes=elements[i].getNodes()
        MatrixCounter=0
        InterfaceCounter=0
        AggregateCounter=0
        Finalresult=''
        nodeNum=len(nodes)

        for node in nodes:
            x_coordinate=node.coordinates[0]
            y_coordinate=node.coordinates[1]
            z_coordinate=node.coordinates[2]
            result=positionResult(x_coordinate,y_coordinate,z_coordinate,sphereData)
            if result=='Matrix':
                MatrixCounter+=1
            elif result=='Interface':
                InterfaceCounter+=1
            elif result=='Aggregate':
                AggregateCounter+=1

        if MatrixCounter==nodeNum:
            Finalresult='Matrix'
        elif AggregateCounter==nodeNum:
            Finalresult='Aggregate'
        else:
            Finalresult='Interface'

        if Finalresult=='Matrix':
            region = regionToolset.Region(elements=elements[i:i+1])
            p.SectionAssignment(region=region, sectionName='SecOf-'+'Matrix-'+str(np.random.randint(0,1000)), offset=0.0, 
            offsetType=MIDDLE_SURFACE, offsetField='', 
            thicknessAssignment=FROM_SECTION)
            if len(MatrixSet)==0:
                MatrixSet=elements[i:i+1]
            else:
                MatrixSet=MatrixSet+elements[i:i+1]

        elif Finalresult=='Aggregate':
            region = regionToolset.Region(elements=elements[i:i+1])
            p.SectionAssignment(region=region, sectionName='SecOf-'+'Aggregate-'+str(np.random.randint(0,1000)), offset=0.0, 
            offsetType=MIDDLE_SURFACE, offsetField='', 
            thicknessAssignment=FROM_SECTION)
            if len(AggregateSet)==0:
                AggregateSet=elements[i:i+1]
            else:
                AggregateSet=AggregateSet+elements[i:i+1]

        elif Finalresult=='Interface':
            region = regionToolset.Region(elements=elements[i:i+1])
            p.SectionAssignment(region=region, sectionName='SecOf-'+'Interface-'+str(np.random.randint(0,1000)), offset=0.0, 
            offsetType=MIDDLE_SURFACE, offsetField='', 
            thicknessAssignment=FROM_SECTION)
            if len(InterfaceSet)==0:
                InterfaceSet=elements[i:i+1]
            else:
                InterfaceSet=InterfaceSet+elements[i:i+1]
    try:
        p.Set(elements=MatrixSet, name='Matrix-Set')
    except:
        pass
    try:
        p.Set(elements=AggregateSet, name='Aggregate-Set')
    except:
        pass
    try:
        p.Set(elements=InterfaceSet, name='Interface-Set')
    except:
        pass


    