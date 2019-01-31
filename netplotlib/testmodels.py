import os

dir_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testcases')
testfiles = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]

content = []
for i in testfiles:
    sbmlstr = open(os.path.join(dir_path, i), 'r')
    content.append(sbmlstr.read())
    sbmlstr.close()

list_models = [s for s in testfiles if "test_list1" in s]
_LIST1 = []
for i in range(len(list_models)):
    sbmlstr = open(os.path.join(dir_path, list_models[i]), 'r')
    _LIST1.append(sbmlstr.read())
    sbmlstr.close()

class testmodels():

    ASPARTATE = content[testfiles.index('test_AspartateMetabolism.xml')]
    BIBI = content[testfiles.index('test_bibi.xml')]
    MAPKCASCADE1 = content[testfiles.index('test_BIOMD0000000010.xml')]
    REPRESSILATOR = content[testfiles.index('test_BIOMD0000000012.xml')]
    EGFMAPK = content[testfiles.index('test_BIOMD0000000019.xml')]
    EGFINSULIN = content[testfiles.index('test_BIOMD0000000223.xml')]
    BIUNI = content[testfiles.index('test_biuni.xml')]
    BRANCHED = content[testfiles.index('test_branched.xml')]
    CONSERVEDCYCLE = content[testfiles.index('test_conservedcycle.xml')]
    FEEDBACK = content[testfiles.index('test_feedback.xml')]
    GALACTOSE = content[testfiles.index('test_galactose.xml')]
    GLYCOLYSIS = content[testfiles.index('test_glycolysis.xml')]
    REVERSIBLE = content[testfiles.index('test_reversible.xml')]
    STOCH1 = content[testfiles.index('test_stoch1.xml')]
    STOCH2 = content[testfiles.index('test_stoch2.xml')]
    STOCH3 = content[testfiles.index('test_stoch3.xml')]
    SYMPY = content[testfiles.index('test_sympy.xml')]
    TWOCYCLES = content[testfiles.index('test_twocycles.xml')]
    UNDEF = content[testfiles.index('test_undefBoundary.xml')]
    UNIBI = content[testfiles.index('test_unibi.xml')]
    LIST1 = _LIST1
    
        
        