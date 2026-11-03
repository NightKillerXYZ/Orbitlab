from orbitlab_backend.frontstep.prompt_builder import build_canonical_prompt

def test_base_sentence():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136,"eccentricity":0.01,"inclinationDeg":28.5,"raanDeg":10,"argumentOfPeriapsisDeg":20,"trueAnomalyDeg":30,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[],"cartesian":None})
    assert "Configure experiment MyExp for SC_MySat, dry mass 500 kg, in a Earth orbit with semi-major axis 6778.136 km and eccentricity 0.01, inclination 28.5 degrees, RAAN 10 degrees, argument of periapsis 20 degrees, and true anomaly 30 degrees; propagate for 2 hours using integrator RungeKutta89." in p
    assert "Use the model's default force settings." in p

def test_forces_explicit():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":{"gravityDegree":8,"gravityOrder":8,"pointMasses":["Luna","Sun"],"solarRadiationPressure":False},"maneuvers":[],"cartesian":None})
    assert "Use a degree-8 and order-8 gravity field, point masses Luna and Sun, and solar radiation pressure off." in p

def test_hohmann():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[{"type":"Hohmann","id":"M1","targetOrbitRadiusKm":8000,"apsis":"periapsis"}],"cartesian":None})
    assert "add maneuver M1: a Hohmann transfer at periapsis to a target orbit radius of 8000 km." in p

def test_hohmann_with_ecc():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":28.5,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[{"type":"Hohmann","id":"M1","targetOrbitRadiusKm":8000,"apsis":"apoapsis","targetEccentricity":0.1}],"cartesian":None})
    assert "target eccentricity 0.1" in p

def test_elapsed_burn():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":0,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[{"type":"ImpulsiveBurn","trigger":"ElapsedTimeSecs","elapsedSecs":120,"deltaV":[0.1,0,0]}],"cartesian":None})
    assert "Give it a small prograde/radial/normal impulse once 120 sec have elapsed: LocalVNB components [0.1, 0, 0] km/s." in p

def test_apsis_burn():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136,"eccentricity":0,"inclinationDeg":0,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[{"type":"ImpulsiveBurn","trigger":"AtApoapsis","apsis":"apoapsis","deltaV":[0.05,0.02,0]}],"cartesian":None})
    assert "At the next apoapsis, apply the LocalVNB burn with V-N-B delta-v [0.05, 0.02, 0] km/s." in p

def test_cartesian():
    p=build_canonical_prompt({"experimentName":"CartExp","spacecraftName":"CartSat","dryMassKg":600,"centralBody":"Earth","semiMajorAxisKm":None,"eccentricity":None,"inclinationDeg":0,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[],"cartesian":{"x":7000,"y":0,"z":0,"vx":0,"vy":7.5,"vz":0}})
    assert "Initial state: r = [7000, 0, 0] km; v = [0, 7.5, 0] km/s in Cartesian coordinates" in p

def test_sma_rounding():
    p=build_canonical_prompt({"experimentName":"MyExp","spacecraftName":"MySat","dryMassKg":500,"centralBody":"Earth","semiMajorAxisKm":6778.136356,"eccentricity":0,"inclinationDeg":0,"raanDeg":0,"argumentOfPeriapsisDeg":0,"trueAnomalyDeg":0,"durationValue":2,"durationUnit":"hours","integrator":"RungeKutta89","forces":None,"maneuvers":[],"cartesian":None})
    assert "6778.136" in p
