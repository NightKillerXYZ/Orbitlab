# v11 eval run — 20261025T184647Z

- cases: `..\..\cases_realistic.jsonl` (30)
- endpoint: model=deepseek-ai/DeepSeek-V4-Flash-0731:deepinfra url=https://router.huggingface.co/v1

## Summary

- passed: 0 / 30
- accuracy: 0.0000

### Per body

| body | n | accuracy |
|---|---|---|
| Earth | 13 | 0.0000 |
| Jupiter | 3 | 0.0000 |
| Mars | 3 | 0.0000 |
| Mercury | 2 | 0.0000 |
| Moon | 4 | 0.0000 |
| Sun | 3 | 0.0000 |
| Venus | 2 | 0.0000 |

### Per category

| category | n | accuracy |
|---|---|---|
| Keplerian | 30 | 0.0000 |

## Failing cases

### R01_ISS (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "R01_ISS",
    "spacecraft": {
      "name": "SC_R01_ISS",
      "dryMass": 419725.0,
      "centralBody": "Earth",
      "orbit": {
        "type": "circular",
        "altitude": 420.0,
        "inclination": 51.64,
        "raan": 120.0,
        "argPeriapsis": 0.0,
        "trueAnomaly": 0.0
      }
    },
    "propagation": {
      "duration": 86400.0,
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "options": {}
  }
}
```

### R02_SSO (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.orbit | unsupported:$.options | unsupported:$.spacecraft.dry_mass_kg
- raw output:

```
{
  "experiment_name": "R02_SSO",
  "spacecraft": {
    "name": "SC_R02_SSO",
    "dry_mass_kg": 950.0
  },
  "orbit": {
    "central_body": "Earth",
    "type": "circular",
    "altitude_km": 700.0,
    "inclination_deg": 98.2,
    "raan_deg": 30.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 90.0
  },
  "propagation": {
    "duration_hours": 12.0,
    "integrator": "RungeKutta89",
    "force_model": "default"
  },
  "options": {}
}
```

### R03_GEO (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "R03_GEO",
    "spacecraft": {
      "name": "SC_R03_GEO",
      "dryMass": 3200,
      "initialState": {
        "frame": "EarthMJ2000Eq",
        "orbit": {
          "type": "Circular",
          "altitude": 35786,
          "inclination": 0.05,
          "raan": 75,
          "argOfPeriapsis": 0,
          "trueAnomaly": 100
        }
      }
    },
    "propagator": {
      "integrator": "PrinceDormand78",
      "stepSize": null,
      "duration": {
        "value": 2,
        "units": "days"
      }
    },
    "forceModel": "default",
    "output": {
      "extraOptions": false
    }
  }
}
```

### R04_Molniya (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment_name": "R04_Molniya",
  "spacecraft": {
    "name": "SC_R04_Molniya",
    "dry_mass": 1600.0,
    "initial_state": {
      "central_body": "Earth",
      "periapsis_altitude_km": 500.0,
      "eccentricity": 0.74,
      "inclination_deg": 63.4,
      "raan_deg": 45.0,
      "arg_periapsis_deg": 270.0,
      "true_anomaly_deg": 0.0
    }
  },
  "propagation": {
    "duration_hours": 24.0,
    "integrator": "PrinceDormand78",
    "force_model": "default"
  },
  "options": {}
}
```
```

### R05_GTO (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "R05_GTO",
    "spacecraft": {
      "name": "SC_R05_GTO",
      "dryMass": 2500.0,
      "initialState": {
        "centralBody": "Earth",
        "frame": "EarthMJ2000Eq",
        "elements": {
          "periapsisAltitude": 250.0,
          "eccentricity": 0.73,
          "inclination": 28.5,
          "raan": 0.0,
          "argPeriapsis": 180.0,
          "trueAnomaly": 0.0
        }
      }
    },
    "propagator": {
      "integrator": "RungeKutta89",
      "stepSize": null,
      "duration": 36000.0,
      "forceModel": "Default"
    },
    "output": {
      "options": []
    }
  }
}
```

### R06_GPS (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "R06_GPS",
    "spacecraft": {
      "name": "SC_R06_GPS",
      "dryMass": 2000.0,
      "initialState": {
        "frame": "EarthMJ2000Eq",
        "orbit": {
          "type": "CIRCULAR",
          "altitude": 20180.0,
          "inclination": 55.0,
          "raan": 60.0,
          "argOfPeriapsis": 0.0,
          "trueAnomaly": 45.0
        }
      }
    },
    "propagation": {
      "duration": 86400.0,
      "integrator": "RungeKutta89",
      "forceModel": "DEFAULT"
    },
    "output": {
      "options": "NONE"
    }
  }
}
```

### R07_Polar (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "R07_Polar",
  "spacecraft": {
    "name": "SC_R07_Polar",
    "dry_mass_kg": 480.0
  },
  "central_body": "Earth",
  "initial_state": {
    "sma_km": 7178.0,
    "eccentricity": 0.001,
    "inclination_deg": 90.0,
    "raan_deg": 200.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 0.0
  },
  "propagation": {
    "duration_hours": 6.0,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "extra_options": false
}
```

### R08_HEO (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.options
- raw output:

```
{
  "experiment_name": "R08_HEO",
  "spacecraft": {
    "name": "SC_R08_HEO",
    "dry_mass_kg": 5200.0
  },
  "central_body": "Earth",
  "initial_state": {
    "periapsis_altitude_km": 1000.0,
    "eccentricity": 0.5,
    "inclination_deg": 63.4,
    "raan_deg": 10.0,
    "arg_periapsis_deg": 270.0,
    "true_anomaly_deg": 20.0
  },
  "propagation": {
    "duration_days": 3.0,
    "integrator": "PrinceDormand78",
    "force_model": "default"
  },
  "options": {}
}
```

### R09_Gravity (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.propagator | unsupported:$.forces | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.initialState
- raw output:

```
{
  "experimentName": "R09_Gravity",
  "spacecraft": {
    "name": "SC_R09_Gravity",
    "dryMass": 650.0,
    "initialState": {
      "coordinateSystem": "EarthFixed",
      "epoch": "2025-01-01T00:00:00.000",
      "stateType": "Keplerian",
      "sma": 6928.14,
      "ecc": 0.0,
      "inc": 97.6,
      "raan": 15.0,
      "argPer": 0.0,
      "trueAnomaly": 0.0
    }
  },
  "propagator": {
    "type": "PrinceDormand78",
    "stepSize": 60.0,
    "duration": 43200.0
  },
  "forces": {
    "gravity": {
      "earth": {
        "degree": 8,
        "order": 8
      },
      "pointMasses": ["Luna", "Sun"]
    },
    "solarRadiationPressure": true
  }
}
```

### R10_NoSRP (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "R10_NoSRP",
    "spacecraft": {
      "name": "SC_R10_NoSRP",
      "dryMass": 1850.0,
      "centralBody": "Earth",
      "initialState": {
        "sma": 7500.0,
        "ecc": 0.02,
        "inc": 45.0,
        "raan": 100.0,
        "argp": 30.0,
        "trueAnomaly": 60.0
      }
    },
    "propagator": {
      "integrator": "RungeKutta89",
      "stepSize": 60.0,
      "duration": 86400.0
    },
    "forceModel": {
      "gravity": {
        "degree": 4,
        "order": 4
      },
      "pointMasses": ["Sun"],
      "solarRadiationPressure": false
    }
  }
}
```
```

### R11_LunarPolar (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.orbit | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "R11_LunarPolar",
  "spacecraft": {
    "name": "SC_R11_LunarPolar",
    "dry_mass_kg": 2200.0
  },
  "central_body": "Moon",
  "orbit": {
    "type": "circular",
    "altitude_km": 100.0,
    "inclination_deg": 90.0,
    "raan_deg": 0.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 0.0
  },
  "propagation": {
    "duration_hours": 8.0,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "extra_options": false
}
```

### R12_LunarFrozen (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "R12_LunarFrozen",
    "spacecraft": {
      "name": "SC_R12_LunarFrozen",
      "dryMass": 1200,
      "centralBody": "Moon",
      "initialState": {
        "sma": 1838,
        "ecc": 0.01,
        "inc": 86,
        "raan": 120,
        "argp": 90,
        "ta": 0
      }
    },
    "propagator": {
      "integrator": "PrinceDormand78",
      "duration": 43200,
      "forceModel": "default"
    },
    "options": {}
  }
}
```
```

### R13_MarsSSO (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.orbit | unsupported:$.options
- raw output:

```
{
  "experiment_name": "R13_MarsSSO",
  "spacecraft": {
    "name": "SC_R13_MarsSSO",
    "dry_mass_kg": 1031.0
  },
  "central_body": "Mars",
  "orbit": {
    "type": "circular",
    "altitude_km": 400.0,
    "inclination_deg": 93.1,
    "raan_deg": 50.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 30.0
  },
  "propagation": {
    "duration_hrs": 12.0,
    "integrator": "RungeKutta89",
    "force_model": "default"
  },
  "options": {}
}
```

### R14_MarsElliptic (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment_name": "R14_MarsElliptic",
  "spacecraft": {
    "name": "SC_R14_MarsElliptic",
    "dry_mass_kg": 2180
  },
  "central_body": "Mars",
  "orbit": {
    "periapsis_altitude_km": 255,
    "eccentricity": 0.0089,
    "inclination_deg": 92.9,
    "raan_deg": 150,
    "arg_periapsis_deg": 270,
    "true_anomaly_deg": 0
  },
  "propagation": {
    "duration_hours": 24,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "options": {}
}
```
```

### R15_MercuryPolar (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "R15_MercuryPolar",
    "spacecraft": {
      "name": "SC_R15_MercuryPolar",
      "dryMass": 507,
      "initialState": {
        "centralBody": "Mercury",
        "periapsisAltitude": 200,
        "eccentricity": 0.74,
        "inclination": 80,
        "raan": 60,
        "argOfPeriapsis": 120,
        "trueAnomaly": 0
      }
    },
    "propagator": {
      "integrator": "PrinceDormand78",
      "duration": 24,
      "durationUnits": "hours"
    },
    "forceModel": "default",
    "output": {
      "extraOptions": false
    }
  }
}
```
```

### R16_VenusPolar (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "R16_VenusPolar",
    "spacecraft": {
      "name": "SC_R16_VenusPolar",
      "dryMass": 1035.0,
      "centralBody": "Venus",
      "initialState": {
        "periapsisAltitude": 250.0,
        "eccentricity": 0.39,
        "inclination": 85.5,
        "raan": 100.0,
        "argOfPeriapsis": 0.0,
        "trueAnomaly": 0.0
      }
    },
    "propagator": {
      "type": "RungeKutta89",
      "stepSize": null,
      "duration": {
        "value": 2.0,
        "unit": "days"
      }
    },
    "forceModel": "default",
    "output": {
      "extraOptions": false
    }
  }
}
```

### R17_JupiterHigh (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.orbit | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "R17_JupiterHigh",
  "spacecraft": {
    "name": "SC_R17_JupiterHigh",
    "dry_mass_kg": 4800
  },
  "central_body": "Jupiter",
  "orbit": {
    "type": "circular",
    "altitude_km": 1000000,
    "inclination_deg": 5,
    "raan_deg": 20,
    "arg_periapsis_deg": 0,
    "true_anomaly_deg": 0
  },
  "propagation": {
    "duration_days": 5,
    "integrator": "PrinceDormand78"
  },
  "force_model": "default",
  "extra_options": false
}
```

### R18_JupiterElliptic (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "R18_JupiterElliptic",
    "spacecraft": {
      "name": "SC_R18_JupiterElliptic",
      "dryMass": 3600.0,
      "centralBody": "Jupiter",
      "orbit": {
        "periapsisAltitude": 150000.0,
        "eccentricity": 0.3,
        "inclination": 25.0,
        "raan": 80.0,
        "argOfPeriapsis": 45.0,
        "trueAnomaly": 0.0
      }
    },
    "propagation": {
      "duration": 10.0,
      "durationUnit": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "options": {}
  }
}
```
```

### R19_Mercurylike (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "R19_Mercurylike",
    "spacecraft": {
      "name": "SC_R19_Mercurylike",
      "dryMass": 600.0
    },
    "centralBody": "Sun",
    "initialState": {
      "sma": 57894375.957,
      "eccentricity": 0.2056,
      "inclination": 7.0,
      "raan": 48.0,
      "argPeriapsis": 29.0,
      "trueAnomaly": 0.0
    },
    "propagation": {
      "duration": 120.0,
      "integrator": "RungeKutta89"
    },
    "forceModel": "default",
    "output": {}
  }
}
```
```

### R20_EarthLike (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "R20_EarthLike",
    "spacecraft": {
      "name": "SC_R20_EarthLike",
      "dryMass": 900.0,
      "wetMass": 900.0
    },
    "centralBody": "Sun",
    "initialState": {
      "sma": 149597870.691,
      "ecc": 0.0167,
      "inc": 0.1,
      "raan": 0.0,
      "argp": 100.0,
      "ta": 0.0
    },
    "propagator": {
      "integrator": "PrinceDormand78",
      "stepSize": null,
      "epoch": null
    },
    "propagationDuration": {
      "value": 180.0,
      "units": "days"
    },
    "forceModel": "default",
    "output": {
      "variables": []
    }
  }
}
```

### X01_Incl270 (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing 'less than or equal to 180'; got errors: ['unsupported:$.experiment']
- raw output:

```
{
  "experiment": {
    "name": "X01_Incl270",
    "spacecraft": {
      "name": "SC_X01_Incl270",
      "dryMass": 420.0,
      "initialState": {
        "frame": "EarthMJ2000Eq",
        "coordinateSystem": "Keplerian",
        "epoch": "2024-01-01T00:00:00.000",
        "sma": 6928.137,
        "ecc": 0.0,
        "inc": 270.0,
        "raan": 40.0,
        "aop": 0.0,
        "ta": 0.0
      }
    },
    "propagator": {
      "type": "RungeKutta89",
      "stepSize": 60.0,
      "duration": 43200.0
    },
    "forceModel": "Default",
    "output": {
      "variables": [
        "SC_X01_Incl270.EarthMJ2000Eq.X",
        "SC_X01_Incl270.EarthMJ2000Eq.Y",
        "SC_X01_Incl270.EarthMJ2000Eq.Z",
        "SC_X01_Incl270.EarthMJ2000Eq.VX",
        "SC_X01_Incl270.EarthMJ2000Eq.VY",
        "SC_X01_Incl270.EarthMJ2000Eq.VZ"
      ]
    }
  }
}
```

### X02_EarthLow (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "below the minimum safe altitude of 100.0 km for central body 'Earth'"; got errors: ['unsupported:$.experiment']
- raw output:

```
{
  "experiment": {
    "name": "X02_EarthLow",
    "spacecraft": {
      "name": "SC_X02_EarthLow",
      "dryMass": 300.0,
      "initialState": {
        "frame": "EarthMJ2000Eq",
        "epoch": "2025-01-01T00:00:00.000",
        "elements": {
          "type": "KEPLERIAN",
          "sma": 6438.137,
          "ecc": 0.0,
          "inc": 51.6,
          "raan": 0.0,
          "argp": 0.0,
          "ta": 0.0
        }
      }
    },
    "propagator": {
      "integrator": "RungeKutta89",
      "stepSize": 60.0,
      "duration": 21600.0
    },
    "forceModel": {
      "useDefault": true
    },
    "output": {
      "type": "default"
    }
  }
}
```

### X03_MoonLow (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "below the minimum safe altitude of 20.0 km for central body 'Moon'"; got errors: ['unsupported:$.experiment_name', 'unsupported:$.central_body', 'unsupported:$.orbit', 'unsupported:$.force_model']
- raw output:

```
{
  "experiment_name": "X03_MoonLow",
  "spacecraft": {
    "name": "SC_X03_MoonLow",
    "dry_mass_kg": 500.0
  },
  "central_body": "Moon",
  "orbit": {
    "type": "circular",
    "altitude_km": 10.0,
    "inclination_deg": 90.0,
    "raan_deg": 0.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 0.0
  },
  "propagation": {
    "duration_hr": 6.0,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "extra_options": "none"
}
```

### X04_MarsLow (expect reject)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment_name": "X04_MarsLow",
  "spacecraft": {
    "name": "SC_X04_MarsLow",
    "dry_mass_kg": 700.0
  },
  "central_body": "Mars",
  "initial_state": {
    "periapsis_altitude_km": 5.0,
    "eccentricity": 0.1,
    "inclination_deg": 60.0,
    "raan_deg": 0.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 0.0
  },
  "propagation": {
    "duration_hours": 6.0,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "options": {}
}
```
```

### X05_VenusLow (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "below the minimum safe altitude of 100.0 km for central body 'Venus'"; got errors: ['unsupported:$.experiment']
- raw output:

```
{
  "experiment": {
    "name": "X05_VenusLow",
    "spacecraft": {
      "name": "SC_X05_VenusLow",
      "dryMass": 800.0,
      "initialState": {
        "centralBody": "Venus",
        "frame": "Inertial",
        "elements": {
          "type": "Classical",
          "sma": 6351.8,
          "ecc": 0.0,
          "inc": 80.0,
          "raan": 0.0,
          "argp": 0.0,
          "nu": 0.0
        }
      }
    },
    "propagator": {
      "integrator": "RungeKutta89",
      "stepSize": 60.0,
      "duration": 21600.0
    },
    "forceModel": "Default",
    "output": {
      "variables": ["Epoch", "SC_X05_VenusLow.EarthMJ2000Eq.X", "SC_X05_VenusLow.EarthMJ2000Eq.Y", "SC_X05_VenusLow.EarthMJ2000Eq.Z", "SC_X05_VenusLow.VenusMJ2000Eq.VX", "SC_X05_VenusLow.VenusMJ2000Eq.VY", "SC_X05_VenusLow.VenusMJ2000Eq.VZ"]
    }
  }
}
```

### X06_JupiterLow (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "below the minimum safe altitude of 1000.0 km for central body 'Jupiter'"; got errors: ['unsupported:$.experiment_name', 'unsupported:$.central_body', 'unsupported:$.orbit', 'unsupported:$.options']
- raw output:

```
{
  "experiment_name": "X06_JupiterLow",
  "spacecraft": {
    "name": "SC_X06_JupiterLow",
    "dry_mass_kg": 3000
  },
  "central_body": "Jupiter",
  "orbit": {
    "type": "circular",
    "altitude_km": 500,
    "inclination_deg": 10,
    "raan_deg": 0,
    "arg_periapsis_deg": 0,
    "true_anomaly_deg": 0
  },
  "propagation": {
    "duration_hours": 6,
    "integrator": "PrinceDormand78",
    "force_model": "default"
  },
  "options": {}
}
```

### X07_MoonSOI (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "escapes the sphere of influence of central body 'Moon'"; got errors: ['unsupported:$.experiment']
- raw output:

```
{
  "experiment": {
    "name": "X07_MoonSOI",
    "spacecraft": {
      "name": "SC_X07_MoonSOI",
      "dryMass": 500.0,
      "initialState": {
        "centralBody": "Moon",
        "frame": "MoonInertial",
        "sma": 90000.0,
        "ecc": 0.1,
        "inc": 30.0,
        "raan": 0.0,
        "aop": 0.0,
        "ta": 0.0
      }
    },
    "propagator": {
      "type": "RungeKutta89",
      "stepSize": null,
      "duration": {
        "value": 2.0,
        "unit": "days"
      }
    },
    "forceModel": "default",
    "output": {
      "extraOptions": false
    }
  }
}
```

### X08_MercurySOI (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "escapes the sphere of influence of central body 'Mercury'"; got errors: ['unsupported:$.experiment']
- raw output:

```
{
  "experiment": {
    "name": "X08_MercurySOI",
    "spacecraft": {
      "name": "SC_X08_MercurySOI",
      "dryMass": 500.0
    },
    "centralBody": "Mercury",
    "initialState": {
      "sma": 200000.0,
      "eccentricity": 0.2,
      "inclination": 30.0,
      "raan": 0.0,
      "argPeriapsis": 0.0,
      "trueAnomaly": 0.0
    },
    "propagation": {
      "duration": 2.0,
      "durationUnit": "days",
      "integrator": "RungeKutta89"
    },
    "forceModel": "default",
    "options": {}
  }
}
```

### X09_SunClose (expect reject)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment_name": "X09_SunClose",
  "spacecraft": {
    "name": "SC_X09_SunClose",
    "dry_mass_kg": 500.0
  },
  "central_body": "Sun",
  "initial_state": {
    "periapsis_altitude_km": 3000000.0,
    "eccentricity": 0.1,
    "inclination_deg": 5.0,
    "raan_deg": 0.0,
    "arg_periapsis_deg": 0.0,
    "true_anomaly_deg": 0.0
  },
  "propagation": {
    "duration_days": 10.0,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "extra_options": "none"
}
```
```

### X10_EarthSOI (expect reject)

- verdict: reject (correct=True)
- json_valid: True
- schema/validated: False
- problem: reject reason missing "escapes the sphere of influence of central body 'Earth'"; got errors: ['unsupported:$.propagator', 'unsupported:$.output', 'unsupported:$.spacecraft.dryMass', 'unsupported:$.spacecraft.initialState']
- raw output:

```
{
  "experimentName": "X10_EarthSOI",
  "spacecraft": {
    "name": "SC_X10_EarthSOI",
    "dryMass": 500,
    "initialState": {
      "centralBody": "Earth",
      "frame": "EarthMJ2000Eq",
      "elements": {
        "type": "Keplerian",
        "sma": 1200000,
        "ecc": 0,
        "inc": 10,
        "raan": 0,
        "argp": 0,
        "trueAnomaly": 0
      }
    }
  },
  "propagator": {
    "type": "RungeKutta89",
    "stepSize": 60,
    "duration": 432000
  },
  "forceModel": "Default",
  "output": {
    "variables": [
      "SC_X10_EarthSOI.EarthMJ2000Eq.X",
      "SC_X10_EarthSOI.EarthMJ2000Eq.Y",
      "SC_X10_EarthSOI.EarthMJ2000Eq.Z",
      "SC_X10_EarthSOI.EarthMJ2000Eq.VX",
      "SC_X10_EarthSOI.EarthMJ2000Eq.VY",
      "SC_X10_EarthSOI.EarthMJ2000Eq.VZ"
    ]
  }
}
```

