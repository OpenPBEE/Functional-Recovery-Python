### ATC-138 Python Numerical Validation Testing Against MATLAB

#### 1. Overview

This documentation provides instructions on how to validate ATC-138 Python implementation against the original MATLAB framework for numerical consistency and correct reproduction of calculations.

The focus is on the standalone use of the comparison engine (`compare_runs.py`) for users who need to validate their own Python and MATLAB models.

The goal is to:
- Explain the testing metrics used
- Outline the testing workflow

This workflow is independent of the integration tests and can be applied to any model. Two example models are included here for demonstration purposes.

#### 2. Example Models Used 

| Model | Description |
|------|-------------|
| ICSB | 6-story special moment frame |
| haseltonRCMF_4story | 4-story reinforced concrete moment frame building |


#### 3. Validation Workflow

1. Run the MATLAB ATC-138 implementation using the provided example inputs.
2. Run the Python ATC-138 implementation using the same demand/data. 
3. Extract both output files `recovery_outputs`. 
4. Compare Python and MATLAB outputs using quantitative metrics using `compare_runs.py`.
5. Evaluate whether results fall within acceptable tolerance thresholds.

#### 4. Comparison Metrics

Four quantitative metrics are used to evaluate agreement between MATLAB and Python results:

</br>

**Metric 1 — Absolute difference of mean functional recovery time**

```| mean_FR_python − mean_FR_matlab |```

Units: ```days```

Threshold: ```≤ 2 days```

</br>

**Metric 2 — Relative difference of mean functional recovery time**

```| mean_FR_python − mean_FR_matlab | / mean_FR_matlab```

Units: ```percent```

Threshold: ```≤ 4 %```

</br>

**Metric 3 — Worst system mean absolute error (MAE)**

System-level wise, the maximum MAE of the fraction of unresolved damage over time, across all functional-recovery and reoccupancy systems. 

Threshold: ```≤ 0.02``` (maximum mean difference of 2% unresolved fraction)

</br>

**Metric 4 — Worst system 95th percentile absolute error**

System-level wise, the maximum 95th percentile aboslute error of the fraction of unresolved damage over time, across all functional-recovery and reoccupancy systems. 

Threshold: ```≤ 0.04``` (maximum mean difference of 4% unresolved fraction)

</br>

#### 5. Recovery Trajectory and System-Level Recovery Comparison

For each model, plots of recovery trajectories and system-level recovery curves are saved: 

- `recovery_trajectory.jpg`
- `system_breakdowns_functional.jpg`
- `system_breakdowns_reoccupancy.jpg`


#### 6. Validation Results

The comparison results for the two example models are summarized below. Twenty batch runs were carried out for each model, and the mean values are compared against the defined metrics.

| Model | Absolute difference (days) | Relative difference (%) | Worst system MAE | Worst system P95 |
|------|------|------|------|------|
| ICSB | 1.38 | 0.241 | 0.015 | 0.030 |
| haseltonRCMF_4story | 1.74 | 1.61 | 0.007 | 0.027 |


All comparison metrics here fall within the defined tolerance thresholds.