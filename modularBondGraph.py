""" Tools for building modular bond graphs.
"""
import BondGraphTools as bgt
import sympy as sp
import copy
import importlib as imp

## Import RE if it exists
spam_spec = imp.util.find_spec("RE")
found = spam_spec is not None
if found:
    import RE
else:
    print('Module RE does not exist (only needed for ReRE)')

def setStr():
    """ Create component strings
    """
    junStr = ("\n## Junction {1}:{0}\n"
              "{0} = bgt.new('{1}',name='{0}')\n"
              "bgt.add(model,{0})\n"
    )
    
    CeStr = ("\n## Component Ce:{0}\n"
             "K_{0} =  sp.symbols('K_{0}')\n"
             "RT = sp.symbols('RT')\n"
             "{0} = bgt.new('Ce',name='{0}',value={{'k':K_{0},'R':RT,'T':1}},library='BioChem')\n"
             "bgt.add(model,{0})\n"
    )

    ReStr = ("\n### Re:{0}\n"
             "\n## Component Re:{0}\n"
             "kappa_{0} =  sp.symbols('kappa_{0}')\n"
             "RT = sp.symbols('RT')\n"
             "{0} = bgt.new('Re',name='{0}',value={{'r':kappa_{0},'R':RT,'T':1}},library='BioChem')\n"
             "bgt.add(model,{0})\n"
    )

    bondStr = "bgt.connect({0},{1})\n"


    return junStr, CeStr, bondStr, ReStr

def findAttached(module,name,end=None):
    """ Find name of component attached to component:name in module """

    nameAttached = None
    for bond in module.bonds:
        if not end=='tail':
            if bond.head.component.name is name:
                nameAttached = bond.tail.component.name

        if not end=='head':
            if bond.tail.component.name is name:
                nameAttached = bond.head.component.name
                
    return nameAttached

def unify(model,common=[],metamodel="C",quiet=False):
    """ Unify C components (species) listed in common
    """
    ## Setup strings
    junStr, CeStr, bondStr, ReStr = setStr()

    if not quiet:
        print("Unifying components in:", model.name)

        
    ## Create the common components at this level
    for Name in common:
        junName = Name+'_jun'
        if not quiet:
            print("Creating:", "Ce:"+Name, "and", "0:"+junName, "in", model.name)
        exec(CeStr.format(Name))
        exec(junStr.format(junName,'0'))
        exec(bondStr.format(junName,Name))
        
    ## Replace common components in subsystems by ports
    for subsystem in model.components:
        #print(subsystem.metamodel,subsystem.name)
        
        if subsystem.metamodel in ["BG"]:
             for comp in subsystem.components:
                if comp.metamodel in ["BG"]:
                    if not quiet:
                        print("unify:",comp.name)
                    #unify(comp,common=common,metamodel=metamodel)

                if ((comp.metamodel in [metamodel]) and
                    (comp.name in common)):
                    #out = compPort(subsystem,comp)
                    #print("Replacing", subsystem.name,":",comp.name,
                    #      "with a port.")
                    ## Expose as port
                    bgt.expose(comp,comp.name)

                    ## Connect port to junction
                    port = (subsystem,comp.name)
                    junName = comp.name+'_jun'
                    for com in  model.components:
                        if com.name in [junName]:
                            jun = com
                    bgt.connect(port,jun)

                    if not quiet:
                        print("Exposing:","Ce:"+comp.name,"in",subsystem.name, "and connecting to", "0:"+jun.name)

def create(name,comp,chain,quiet=False):
    #print(name,comp,comp.name,comp.metamodel)
    # if comp.metamodel == 'BG':
    #     #print(comp.bonds)
    if not quiet:
        print("Creating", name, "from", comp.name, "within", chain.name)
    exec(name+" = copy.deepcopy(comp)")
    exec(name+".name = '"+name+"'")
    exec("chain.add("+name+")")

    #print(chain.components[0].bonds)

def rename_instance(model,i,inport,outport,Comps=['C','R'],quiet=False):
    """Rename all non-port components in an instance indexed by i
    """

    comps = []
    for comp in model.components:
        if comp.metamodel in Comps:
            name = comp.name
            comps.append(name)
    #print(comps)
    renames = {}
    for comp in comps:
        renames[comp] = comp+'_'+str(i)
    #print(renames)
    rename(model,renames,quiet=quiet)
    
def chain(model0,inport='in',outport='out',N=2,
          rename_components=True,Comps=['R','C'],quiet=False):
    """ Concatenate N instances of model via ports inport and outport
        The ports are represented in model as Ce components
        Ce:in in the first link of the chain and Ce:out in the last link remain as Ce components
        The method unifies Ce:out of link i and Ce:in of link i+1 by replacing them by ports 
        and connecting them to a new Ce component with associated zero junction.
    """

    model = copy.deepcopy(model0)
    
    intname = "IS"
    name = model.name+"Chain"
    
    ## Turn chemostats into ports
    compIn = copy.deepcopy(model / inport) # Clone component at inport
    compOut = copy.deepcopy(model / outport) # Clone component at outport
    nameFirst = model.name+"0"
    nameLast = model.name+str(N-1)
    nameIn = compIn.name
    nameOut = compOut.name
    
    IS =  model / inport       # Intermediate Ce
    
    if not quiet:
        print("Exposing",inport, "and", outport)
    bgt.expose(model / inport, "in") # Create in port
    bgt.expose(model / outport, "out") # Create outport

    ## Create the chain
    if not quiet:
        print("Creating",name)
    chain = bgt.new(name=name)
    zero = bgt.new('0')
    for i in range(N):
        ## Create the components
        cname = model.name+str(i)
        Model = copy.deepcopy(model)
        # print('model.bonds:', model.bonds)
        # print('Model.bonds:', Model.bonds)
        if rename_components:
            rename_instance(Model,i,inport,outport,Comps=Comps,quiet=quiet)
        create(cname,Model,chain,quiet=quiet)

        if i>0:
            ## Create the intermediate species
            ISname = intname+str(i)
            zeroname = "j"+ISname
            zero = bgt.new('0')
            create(ISname,IS,chain,quiet=quiet)
            create(zeroname,zero,chain,quiet=quiet)

            ## And connect
            previous = model.name+str(i-1)
            bgt.connect(chain / zeroname,chain / ISname)
            bgt.connect(chain / zeroname,(chain / cname,"in"))
            bgt.connect((chain / previous,'out'),chain / zeroname)

    ## Set up the two ends
    jnameIn = "j"+nameIn
    create(nameIn,IS,chain,quiet=quiet)
    create(jnameIn,zero,chain,quiet=quiet)
    bgt.connect(chain / jnameIn, chain / nameIn)
    bgt.connect(chain / jnameIn, (chain / nameFirst, "in"))

    jnameOut = "j"+nameOut
    create(nameOut,IS,chain,quiet=quiet)
    create(jnameOut,zero,chain,quiet=quiet)
    bgt.connect(chain / jnameOut, chain / nameOut)
    bgt.connect((chain / nameLast, "out"), chain / jnameOut)

    return chain

def split(model,quiet=False):
    """ Split reactions into two and joined by complex
    """
    ## Setup strings
    junStr, CeStr, bondStr, ReStr = setStr()

    if not quiet:
        print("Splitting reactions in:", model.name)
        
    components = copy.copy(model.components)
    for component in components:
        if component.metamodel in ["R"]:
            if not quiet:
                Name = component.name
                junName = Name+'_jun'
                cName = "C"+Name
                rName = Name+Name
                print("Splitting", component.name)
                exec(CeStr.format(cName))
                exec(junStr.format(junName,"0"))
                exec(ReStr.format(rName))
                exec(bondStr.format(junName,cName))
                exec(bondStr.format(junName,rName))

                for bond in model.bonds:
                    if bond.tail.component.name is Name:
                        bgt.disconnect(bond.tail,bond.head)
                        bgt.connect(bond.tail.component,model / junName)
                        bgt.connect((model / rName,1), bond.head.component)

def setValue(module,names,quiet=False):
    """ Resets value of  components within module according to dict names
    """
    
    if not quiet:
        print("Renaming components within", module.name)

    for key,value in names.items():
        if not quiet:
            print("Setting parameter", value[0], "of", key, "to", value[1])
            #print((module/key).params)
            
def rename(module,names,quiet=False):
    """ Renames components within module according to dict names
    """

    if not quiet:
        print("Renaming components within", module.name)
        
    ## Find list of all names in this module
    nameList = []
    for comp in module.components:
        if not comp.metamodel in ["0","1"]:
            #print(comp.metamodel,comp.name)
            nameList.append(comp.name)

    for key, name in names.items():
        if not name in nameList:
            if not quiet:
                print("\tRenaming",key,"to",name)
            (module / key).name = name
        else:
            print("\t"+name, "exists in", module.name+": connecting")
            
            ## Find what current components called key and name are attached to
            for bond in module.bonds:
                if bond.head.component.name is name:
                    nameJun = bond.tail.component
                if bond.head.component.name is key:
                    keyJun = bond.tail.component

            keyComp = module / key
            bgt.connect(keyJun,nameJun)
            bgt.disconnect(keyJun,keyComp)
            module.remove(keyComp)

def renameSub(module,portList=[],quiet=True):
    """ Rename all non-port components in module to moduleName_compName"""

    modName = module.name
    if not quiet:
        print("Renaming components in:",modName)

    renames = {}
    for comp in module.components:
        if comp.metamodel in ['R','C']:
            compName = comp.name
            if compName not in portList:
                newname = modName+'_'+compName
                if not quiet:
                    print("Renaming component:",compName,'('+comp.metamodel+') to ',newname)

                renames[compName] = newname

    rename(module,renames,quiet=quiet)
                
    
    

def changeStoich(module,names,quiet=False):
    """ Changes Ce stoichiometry  within module according to dict names
    """

    if not quiet:
        print("Changing stoichiometry components within", module.name)
        
    ## Find list of all names in this module
    TFlist = []
    for comp in module.components:
        if comp.metamodel in ["TF"]:
            TFlist.append(comp.name)
        CeList = []
        if comp.metamodel in ["C"]:
            CeList.append(comp.name)
            
    for key, val in names.items():
        TFname = key+"_TF"
        if TFname in TFlist:
            if not quiet:
                print("\tChanging stoichiometry of",key,"to",val)
                
            (module/TFname).params['r'] = val
        else:
            if key in CeList:
                print('Component Ce:'+key, 'does not have variable stoichiometry, missing :?')
            else:
                print('Component Ce:'+key, 'does not exist within', module.name)


def sink(model,names=[]):
    """ Connect the Ces listed in names to a zero sink """

    ## Set up strings
    junStr, CeStr, bondStr, ReStr = setStr()

    ## Create the sink: Ce + Re + 0 junction
    zeroName = "Zero"
    zeroJunName = zeroName+"Jun"
    exec(CeStr.format(zeroName))
    exec(junStr.format(zeroJunName,"0"))
    bgt.connect(model/zeroJunName,model/zeroName)
    
    ## Connect the components listed in names via Re component
    for name in names:
        zeroReName = name+zeroName+"Re"
        junName = findAttached(model,name)
        exec(ReStr.format(zeroReName))
        bgt.connect(model/junName,model/zeroReName)
        bgt.connect(model/zeroReName,model/zeroJunName)

def modulate(sys,reaction):
    """ Add modulation to each listed reaction """

    ## Setup strings
    junStr, CeStr, bondStr, ReStr = setStr()
    
    model = copy.copy(sys)
    # print(model.components)
    # print(model / 'comp_ROS2_junF')

    mod_str = ''
    for reac in reaction:
        Name = 'mod_'+reac
        junName = Name+'_jun'
        forwardName = 'comp_'+reac+'_junF'
        reverseName = 'comp_'+reac+'_junR'
        
        mod_str += f'## Adding modulation {Name}\n'
        mod_str += CeStr.format(Name)
        mod_str += junStr.format(junName,'0')
        mod_str += bondStr.format(junName,Name)
        mod_str += bondStr.format(junName,forwardName)
        mod_str += bondStr.format(reverseName,junName)

    return mod_str

def ReRE(model,quiet=False):

    SfStr = "{0} = bgt.new('Sf',name='{0}')\n"
    components = copy.copy(model.components)
    #print(model.bonds)
    for comp in components:
        if comp.metamodel in ['BG']:
            replaceRe(comp,quiet=quiet)
            
        if comp.metamodel in ['R']:
            
            name = comp.name
            if not quiet:
                print(f"Swapping Re:{name} for RE:{name} in {model.name}")
            
            ## Find what it is connected to, and disconnect
            forward_comp = None
            reverse_comp = None
            bonds = copy.copy(model.bonds) # ????
            for bond in bonds:
                ## Forward connection
                if bond.head.component.name is comp.name:
                    forward_comp = bond.tail.component
                    # print("forward:", forward_comp, bond.tail) 
                    bgt.disconnect(forward_comp,comp)

                    
                ## Reverse connection
                if bond.tail.component.name is comp.name:
                    reverse_comp = bond.head.component
                    # print ("reverse:",reverse_comp)
                    bgt.disconnect(comp,reverse_comp)
                        
            ## Remove the Re
            name = comp.name;
            bgt.remove(model, comp)
                        
            ## Add the new RE component
            new_comp = RE.model()
            new_comp.name = name
            renameSub(new_comp,portList=['A','B'],quiet=quiet)
            bgt.add(model,new_comp)

            ## Expose the ports
            bgt.expose(new_comp / 'A',label='A')
            bgt.expose(new_comp / 'B',label='B')
                        
            if not forward_comp is None:
                bgt.connect(forward_comp,(new_comp,'A'))
            else:
                print('No forward component')
                
            if not reverse_comp is None:
                bgt.connect((new_comp,'B'),reverse_comp)
            else:
                print('No reverse component')

    return model
