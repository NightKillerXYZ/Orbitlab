# v11 eval run — 20261025T184643Z

- cases: `cases_blind.jsonl` (32)
- endpoint: model=deepseek-ai/DeepSeek-V4-Flash-0731:deepinfra url=https://router.huggingface.co/v1

## Summary

- passed: 0 / 32
- accuracy: 0.0000

### Per body

| body | n | accuracy |
|---|---|---|
| Jupiter | 8 | 0.0000 |
| Mercury | 8 | 0.0000 |
| Sun | 8 | 0.0000 |
| Venus | 8 | 0.0000 |

### Per category

| category | n | accuracy |
|---|---|---|
| Keplerian | 32 | 0.0000 |

## Failing cases

### BlindMerc_001 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.orbit | unsupported:$.output
- raw output:

```
{
  "experiment_name": "BlindMerc_001",
  "spacecraft": {
    "name": "SCBlindMerc_001",
    "dry_mass_kg": 517.34
  },
  "central_body": "Mercury",
  "orbit": {
    "type": "circular",
    "altitude_km": 1237.4,
    "inclination_deg": 19.37,
    "raan_deg": 41.8,
    "arg_periapsis_deg": 17.2,
    "true_anomaly_deg": 63.5
  },
  "propagation": {
    "duration_hours": 7.5,
    "integrator": "RungeKutta89",
    "force_model": "default"
  },
  "output": {
    "extra_options": false
  }
}
```

### BlindMerc_002 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.propagator | unsupported:$.output | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.initialState
- raw output:

```
{
  "experimentName": "BlindMerc_002",
  "spacecraft": {
    "name": "SCBlindMerc_002",
    "dryMass": 783.91,
    "initialState": {
      "centralBody": "Mercury",
      "frame": "Inertial",
      "elements": {
        "type": "Keplerian",
        "altitude": 2843.17,
        "inclination": 43.82,
        "raan": 107.4,
        "argPeriapsis": 89.6,
        "trueAnomaly": 134.1
      }
    }
  },
  "propagator": {
    "integrator": "PrinceDormand78",
    "duration": 1.75,
    "durationUnit": "days",
    "forceModel": "default"
  },
  "output": {
    "extraOptions": false
  }
}
```

### BlindMerc_003 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindMerc_003",
    "spacecraft": {
      "name": "SCBlindMerc_003",
      "dryMass": 1049.62
    },
    "centralBody": "Mercury",
    "initialState": {
      "orbit": {
        "type": "circular",
        "altitude": 5192.85,
        "inclination": 77.14,
        "raan": 193.7,
        "argOfPeriapsis": 161.3,
        "trueAnomaly": 218.9
      }
    },
    "propagation": {
      "duration": 4.25,
      "durationUnits": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "output": {
      "extraOptions": false
    }
  }
}
```

### BlindMerc_004 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.propagator | unsupported:$.output | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.centralBody
- raw output:

```
{
  "experimentName": "BlindMerc_004",
  "spacecraft": {
    "name": "SCBlindMerc_004",
    "dryMass": 1318.47,
    "centralBody": "Mercury",
    "initialState": {
      "periapsisAltitude": 312.67,
      "eccentricity": 0.0731,
      "inclination": 94.63,
      "raan": 251.2,
      "argPeriapsis": 233.8,
      "trueAnomaly": 279.4
    }
  },
  "propagator": {
    "integrator": "PrinceDormand78",
    "duration": 3.25,
    "durationUnit": "days"
  },
  "forceModel": "default",
  "output": {
    "extraOptions": false
  }
}
```

### BlindMerc_005 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "BlindMerc_005",
  "spacecraft": {
    "name": "SCBlindMerc_005",
    "dry_mass_kg": 1587.19
  },
  "central_body": "Mercury",
  "initial_state": {
    "periapsis_altitude_km": 847.23,
    "eccentricity": 0.1342,
    "inclination_deg": 119.28,
    "raan_deg": 309.5,
    "arg_periapsis_deg": 297.1,
    "true_anomaly_deg": 341.7
  },
  "propagation": {
    "duration_days": 5.75,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "output": {
    "extra_options": false
  }
}
```

### BlindMerc_006 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.output
- raw output:

```
{
  "experiment_name": "BlindMerc_006",
  "spacecraft": {
    "name": "SCBlindMerc_006",
    "dry_mass_kg": 1842.56
  },
  "central_body": "Mercury",
  "initial_state": {
    "periapsis_altitude_km": 1623.89,
    "eccentricity": 0.1875,
    "inclination_deg": 136.45,
    "raan_deg": 27.9,
    "arg_periapsis_deg": 43.4,
    "true_anomaly_deg": 52.8
  },
  "propagation": {
    "duration_days": 6.25,
    "integrator": "PrinceDormand78",
    "force_model": "default"
  },
  "output": {
    "extra_options": false
  }
}
```

### BlindMerc_007 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "BlindMerc_007",
  "spacecraft": {
    "name": "SCBlindMerc_007",
    "dry_mass_kg": 2104.83
  },
  "central_body": "Mercury",
  "initial_state": {
    "sma_km": 4187.65,
    "eccentricity": 0.0914,
    "inclination_deg": 152.71,
    "raan_deg": 83.6,
    "arg_periapsis_deg": 114.9,
    "true_anomaly_deg": 147.3
  },
  "propagation": {
    "duration_days": 7.25,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "extra_options": false
}
```

### BlindMerc_008 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindMerc_008",
    "spacecraft": {
      "name": "SCBlindMerc_008",
      "dryMass": 2379.12,
      "wetMass": 2379.12
    },
    "centralBody": "Mercury",
    "propagator": {
      "integrator": "PrinceDormand78",
      "stepSize": null,
      "epoch": null
    },
    "initialState": {
      "frame": "MJ2000Eq",
      "sma": 6843.92,
      "ecc": 0.2163,
      "inc": 169.34,
      "raan": 149.1,
      "argp": 187.5,
      "ta": 231.6
    },
    "duration": {
      "value": 8.75,
      "units": "days"
    },
    "forceModel": "default",
    "output": {
      "variables": []
    }
  }
}
```

### BlindVen_009 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.propagator | unsupported:$.output | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.initialState
- raw output:

```
{
  "experimentName": "BlindVen_009",
  "spacecraft": {
    "name": "SCBlindVen_009",
    "dryMass": 563.78,
    "initialState": {
      "centralBody": "Venus",
      "orbitType": "Circular",
      "altitude": 1437.6,
      "inclination": 21.49,
      "raan": 53.2,
      "argOfPeriapsis": 29.8,
      "trueAnomaly": 74.3
    }
  },
  "propagator": {
    "integrator": "RungeKutta89",
    "stepSize": null,
    "duration": {
      "value": 9.5,
      "unit": "hours"
    }
  },
  "forceModel": "default",
  "output": {
    "extraOptions": false
  }
}
```

### BlindVen_010 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "BlindVen_010",
    "spacecraft": {
      "name": "SCBlindVen_010",
      "dryMass": 841.29,
      "centralBody": "Venus",
      "orbit": {
        "type": "circular",
        "altitude": 4782.35,
        "inclination": 46.73,
        "raan": 118.9,
        "argOfPeriapsis": 97.4,
        "trueAnomaly": 142.8
      }
    },
    "propagation": {
      "duration": 2.25,
      "durationUnits": "days",
      "integrator": "PrinceDormand78",
      "forceModel": "default"
    },
    "options": {}
  }
}
```
```

### BlindVen_011 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindVen_011",
    "spacecraft": {
      "name": "SCBlindVen_011",
      "dryMass": 1129.64,
      "centralBody": "Venus",
      "orbit": {
        "type": "circular",
        "altitude": 13489.7,
        "inclination": 79.85,
        "raan": 204.3,
        "argPeriapsis": 173.6,
        "trueAnomaly": 226.1
      }
    },
    "propagation": {
      "duration": 4.75,
      "durationUnit": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "options": {}
  }
}
```

### BlindVen_012 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment_name": "BlindVen_012",
  "spacecraft": {
    "name": "SCBlindVen_012",
    "dry_mass_kg": 1417.53
  },
  "central_body": "Venus",
  "initial_state": {
    "periapsis_altitude_km": 612.84,
    "eccentricity": 0.0842,
    "inclination_deg": 98.12,
    "raan_deg": 263.7,
    "arg_periapsis_deg": 241.9,
    "true_anomaly_deg": 287.5
  },
  "propagation": {
    "duration_days": 3.75,
    "integrator": "PrinceDormand78"
  },
  "force_model": "default",
  "output_options": "none"
}
```
```

### BlindVen_013 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "BlindVen_013",
    "spacecraft": {
      "name": "SCBlindVen_013",
      "dryMass": 1692.81
    },
    "centralBody": "Venus",
    "initialState": {
      "periapsisAltitude": 2184.56,
      "eccentricity": 0.1463,
      "inclination": 121.67,
      "raan": 319.4,
      "argPeriapsis": 308.2,
      "trueAnomaly": 349.6
    },
    "propagation": {
      "duration": 6.25,
      "durationUnit": "days",
      "integrator": "RungeKutta89"
    },
    "forceModel": "default",
    "options": {}
  }
}
```
```

### BlindVen_014 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.propagator | unsupported:$.output | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.centralBody
- raw output:

```
{
  "experimentName": "BlindVen_014",
  "spacecraft": {
    "name": "SCBlindVen_014",
    "dryMass": 1974.38,
    "centralBody": "Venus",
    "initialState": {
      "periapsisAltitude": 4912.73,
      "eccentricity": 0.2184,
      "inclination": 139.54,
      "raan": 37.8,
      "argOfPeriapsis": 54.7,
      "trueAnomaly": 61.2
    }
  },
  "propagator": {
    "integrator": "PrinceDormand78",
    "duration": 7.75,
    "durationUnit": "days"
  },
  "forceModel": "default",
  "output": {
    "extraOptions": false
  }
}
```

### BlindVen_015 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "BlindVen_015",
    "spacecraft": {
      "name": "SCBlindVen_015",
      "dryMass": 2248.95,
      "massUnit": "kg"
    },
    "centralBody": "Venus",
    "initialState": {
      "sma": 12784.63,
      "smaUnit": "km",
      "eccentricity": 0.1127,
      "inclination": 154.89,
      "inclinationUnit": "deg",
      "raan": 94.1,
      "raanUnit": "deg",
      "argPeriapsis": 126.3,
      "argPeriapsisUnit": "deg",
      "trueAnomaly": 158.4,
      "trueAnomalyUnit": "deg"
    },
    "propagation": {
      "duration": 8.25,
      "durationUnit": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "options": {}
  }
}
```
```

### BlindVen_016 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindVen_016",
    "spacecraft": {
      "name": "SCBlindVen_016",
      "dryMass": 2519.42,
      "centralBody": "Venus",
      "initialState": {
        "sma": 21493.28,
        "ecc": 0.2341,
        "inc": 170.42,
        "raan": 161.5,
        "argp": 198.7,
        "ta": 243.9
      }
    },
    "propagator": {
      "integrator": "PrinceDormand78",
      "stepSize": null,
      "duration": 9.25,
      "durationUnit": "days"
    },
    "forceModel": "default",
    "output": {
      "extraOptions": false
    }
  }
}
```

### BlindJup_017 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindJup_017",
    "spacecraft": {
      "name": "SCBlindJup_017",
      "dryMass": 934.67,
      "centralBody": "Jupiter",
      "orbit": {
        "type": "Circular",
        "altitude": 14832.5,
        "inclination": 23.64,
        "raan": 49.3,
        "argOfPeriapsis": 31.7,
        "trueAnomaly": 81.2
      }
    },
    "propagation": {
      "duration": 2.75,
      "durationUnit": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "options": {}
  }
}
```

### BlindJup_018 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment_name": "BlindJup_018",
  "spacecraft": {
    "name": "SCBlindJup_018",
    "dry_mass": 1289.45,
    "central_body": "Jupiter",
    "orbit": {
      "type": "circular",
      "altitude": 142780.3,
      "altitude_units": "km",
      "inclination": 54.18,
      "inclination_units": "deg",
      "raan": 127.6,
      "raan_units": "deg",
      "arg_periapsis": 103.9,
      "arg_periapsis_units": "deg",
      "true_anomaly": 154.7,
      "true_anomaly_units": "deg"
    }
  },
  "propagation": {
    "duration": 6.75,
    "duration_units": "days",
    "integrator": "PrinceDormand78",
    "force_model": "default"
  },
  "options": {}
}
```
```

### BlindJup_019 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "BlindJup_019",
    "spacecraft": {
      "name": "SCBlindJup_019",
      "dryMass": 1643.82,
      "wetMass": 1643.82
    },
    "centralBody": "Jupiter",
    "orbit": {
      "type": "circular",
      "altitude": 893450.8,
      "inclination": 83.91,
      "raan": 213.4,
      "argOfPeriapsis": 179.2,
      "trueAnomaly": 233.6
    },
    "propagation": {
      "duration": 13.5,
      "durationUnit": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "options": {}
  }
}
```
```

### BlindJup_020 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "BlindJup_020",
  "spacecraft": {
    "name": "SCBlindJup_020",
    "dry_mass_kg": 1998.14
  },
  "central_body": "Jupiter",
  "initial_state": {
    "periapsis_altitude_km": 23480.6,
    "eccentricity": 0.0925,
    "inclination_deg": 101.47,
    "raan_deg": 271.8,
    "arg_of_periapsis_deg": 248.5,
    "true_anomaly_deg": 294.1
  },
  "propagation": {
    "duration_days": 5.25,
    "integrator": "PrinceDormand78"
  },
  "force_model": "default",
  "output_options": "none"
}
```

### BlindJup_021 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.initial_state | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "BlindJup_021",
  "spacecraft": {
    "name": "SCBlindJup_021",
    "dry_mass_kg": 2354.76
  },
  "central_body": "Jupiter",
  "initial_state": {
    "periapsis_altitude_km": 118420.4,
    "eccentricity": 0.1638,
    "inclination_deg": 124.83,
    "raan_deg": 327.1,
    "arg_periapsis_deg": 314.6,
    "true_anomaly_deg": 353.8
  },
  "propagation": {
    "duration_days": 9.75,
    "integrator": "RungeKutta89"
  },
  "force_model": "default",
  "output_options": "none"
}
```

### BlindJup_022 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindJup_022",
    "spacecraft": {
      "name": "SCBlindJup_022",
      "dryMass": 2712.39,
      "centralBody": "Jupiter"
    },
    "initialState": {
      "frame": "JupiterInertial",
      "elements": {
        "periapsisAltitude": 412890.7,
        "eccentricity": 0.2415,
        "inclination": 142.19,
        "raan": 43.5,
        "argPeriapsis": 61.8,
        "trueAnomaly": 69.4
      }
    },
    "propagation": {
      "duration": 14.25,
      "durationUnits": "days",
      "integrator": "PrinceDormand78",
      "forceModel": "default"
    },
    "output": {
      "options": "none"
    }
  }
}
```

### BlindJup_023 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindJup_023",
    "spacecraft": {
      "name": "SCBlindJup_023",
      "dryMass": 3068.51,
      "wetMass": 3068.51,
      "fuelMass": 0.0
    },
    "centralBody": "Jupiter",
    "initialState": {
      "sma": 384920.6,
      "ecc": 0.1284,
      "inc": 158.76,
      "raan": 101.2,
      "argp": 133.4,
      "trueAnomaly": 164.9,
      "frame": "J2000"
    },
    "propagator": {
      "integrator": "RungeKutta89",
      "stepSize": null,
      "accuracy": null
    },
    "duration": {
      "value": 16.5,
      "units": "days"
    },
    "forceModel": "default",
    "output": {
      "variables": []
    }
  }
}
```

### BlindJup_024 (expect accept)

- verdict: reject (correct=False)
- json_valid: False
- schema/validated: False
- problem: json: Expecting value: line 1 column 1 (char 0)
- raw output:

```
```json
{
  "experiment": {
    "name": "BlindJup_024",
    "spacecraft": {
      "name": "SCBlindJup_024",
      "dryMass": 3425.93,
      "wetMass": 3425.93
    },
    "centralBody": "Jupiter",
    "initialState": {
      "sma": 1482390.4,
      "ecc": 0.2739,
      "inc": 173.15,
      "raan": 168.7,
      "argp": 204.1,
      "ta": 251.3
    },
    "propagation": {
      "duration": 24.5,
      "durationUnits": "days",
      "integrator": "PrinceDormand78"
    },
    "forceModel": "default",
    "output": {
      "extraOptions": false
    }
  }
}
```
```

### BlindSun_025 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.propagator | unsupported:$.output | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.initialState
- raw output:

```
{
  "experimentName": "BlindSun_025",
  "spacecraft": {
    "name": "SCBlindSun_025",
    "dryMass": 612.48,
    "initialState": {
      "centralBody": "Sun",
      "frame": "EME2000",
      "epoch": "2025-01-01T00:00:00.000",
      "sma": 22439680.604,
      "ecc": 0.0,
      "inc": 11.23,
      "raan": 29.4,
      "argp": 19.6,
      "trueAnomaly": 41.8
    }
  },
  "propagator": {
    "type": "RungeKutta89",
    "stepSize": 60.0,
    "duration": 1900800.0
  },
  "forceModel": {
    "centralBodyGravity": true,
    "sunGravity": false,
    "moonGravity": false,
    "solarRadiationPressure": false,
    "drag": false
  },
  "output": {
    "variables": [
      "SCBlindSun_025.EarthMJ2000Eq.X",
      "SCBlindSun_025.EarthMJ2000Eq.Y",
      "SCBlindSun_025.EarthMJ2000Eq.Z",
      "SCBlindSun_025.EarthMJ2000Eq.VX",
      "SCBlindSun_025.EarthMJ2000Eq.VY",
      "SCBlindSun_025.EarthMJ2000Eq.VZ"
    ],
    "file": "BlindSun_025.csv"
  }
}
```

### BlindSun_026 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.name | unsupported:$.propagator | unsupported:$.output | unsupported:$.spacecraft.dryMass
- raw output:

```
{
  "name": "BlindSun_026",
  "spacecraft": {
    "name": "SCBlindSun_026",
    "dryMass": 947.31,
    "centralBody": "Sun",
    "initialState": {
      "sma": 112198403.018,
      "eccentricity": 0,
      "inclination": 33.87,
      "raan": 104.2,
      "argPeriapsis": 87.5,
      "trueAnomaly": 119.3
    }
  },
  "propagator": {
    "integrator": "PrinceDormand78",
    "duration": 85,
    "durationUnit": "days",
    "forceModel": "default"
  },
  "output": {
    "extraOptions": false
  }
}
```

### BlindSun_027 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.options | unsupported:$.spacecraft.dryMass | unsupported:$.spacecraft.centralBody | unsupported:$.spacecraft.initialState
- raw output:

```
{
  "experimentName": "BlindSun_027",
  "spacecraft": {
    "name": "SCBlindSun_027",
    "dryMass": 1284.69,
    "centralBody": "Sun",
    "initialState": {
      "sma": 261796273.709,
      "eccentricity": 0,
      "inclination": 61.42,
      "raan": 189.7,
      "argOfPeriapsis": 158.1,
      "trueAnomaly": 204.6
    }
  },
  "propagation": {
    "duration": 195,
    "durationUnit": "days",
    "integrator": "RungeKutta89",
    "forceModel": "default"
  },
  "options": {}
}
```

### BlindSun_028 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment_name | unsupported:$.central_body | unsupported:$.orbit | unsupported:$.force_model
- raw output:

```
{
  "experiment_name": "BlindSun_028",
  "spacecraft": {
    "name": "SCBlindSun_028",
    "dry_mass_kg": 1619.52
  },
  "central_body": "Sun",
  "orbit": {
    "periapsis_altitude_km": 24830430.5,
    "eccentricity": 0.0812,
    "inclination_deg": 79.64,
    "raan_deg": 247.3,
    "arg_periapsis_deg": 229.4,
    "true_anomaly_deg": 267.8
  },
  "propagation": {
    "duration_days": 48,
    "integrator": "PrinceDormand78"
  },
  "force_model": "default",
  "options": {}
}
```

### BlindSun_029 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindSun_029",
    "spacecraft": {
      "name": "SCBlindSun_029",
      "dryMass": 1953.87,
      "centralBody": "Sun",
      "orbit": {
        "periapsisAltitude": 78420300.2,
        "eccentricity": 0.1475,
        "inclination": 103.18,
        "raan": 304.9,
        "argPeriapsis": 293.7,
        "trueAnomaly": 329.2
      }
    },
    "propagator": {
      "integrator": "RungeKutta89",
      "duration": 115,
      "durationUnit": "days",
      "forceModel": "default"
    },
    "output": {
      "extraOptions": false
    }
  }
}
```

### BlindSun_030 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindSun_030",
    "spacecraft": {
      "name": "SCBlindSun_030",
      "dryMass": 2287.19,
      "centralBody": "Sun",
      "periapsisAltitude": 184930200.6,
      "eccentricity": 0.2134,
      "inclination": 127.53,
      "raan": 21.6,
      "argOfPeriapsis": 47.2,
      "trueAnomaly": 53.9
    },
    "propagator": {
      "type": "PrinceDormand78",
      "duration": 210,
      "durationUnit": "days"
    },
    "forceModel": "default",
    "options": {}
  }
}
```

### BlindSun_031 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindSun_031",
    "spacecraft": {
      "id": "SCBlindSun_031",
      "dryMass": 2614.73,
      "initialState": {
        "centralBody": "Sun",
        "frame": "EME2000",
        "elements": {
          "sma": 173849200.5,
          "ecc": 0.1328,
          "inc": 146.29,
          "raan": 89.4,
          "argp": 118.6,
          "trueAnomaly": 149.1
        },
        "units": {
          "sma": "km",
          "inc": "deg",
          "raan": "deg",
          "argp": "deg",
          "trueAnomaly": "deg"
        }
      }
    },
    "propagation": {
      "duration": 165,
      "durationUnits": "days",
      "integrator": "RungeKutta89",
      "forceModel": "default"
    },
    "output": {
      "extraOptions": false
    }
  }
}
```

### BlindSun_032 (expect accept)

- verdict: reject (correct=False)
- json_valid: True
- schema/validated: False
- problem: expected accept but validator rejected: unsupported:$.experiment
- raw output:

```
{
  "experiment": {
    "name": "BlindSun_032",
    "spacecraft": {
      "name": "SCBlindSun_032",
      "dryMass": 2948.36,
      "massUnit": "kg"
    },
    "centralBody": "Sun",
    "initialState": {
      "sma": 394827100.8,
      "smaUnit": "km",
      "eccentricity": 0.2847,
      "inclination": 164.81,
      "inclinationUnit": "deg",
      "raan": 154.2,
      "raanUnit": "deg",
      "argPeriapsis": 191.3,
      "argPeriapsisUnit": "deg",
      "trueAnomaly": 237.4,
      "trueAnomalyUnit": "deg"
    },
    "propagation": {
      "duration": 285,
      "durationUnit": "days",
      "integrator": "PrinceDormand78",
      "forceModel": "default"
    },
    "options": {}
  }
}
```

