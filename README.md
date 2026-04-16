# Functional-Recovery---Python
This is translation of Matlab codebase into Python for quantifying building-specific functional recovery and reoccupancy based on a probabilistic performance-based earthquake engineering framework.

## Requirements

- **Python Version**: 3.9 or later (recommend 3.9)
- **Package Manager**: pip (comes with Python)

### Installation

The ATC-138 Functional Recovery Assessment tool is distributed as a Python package. Install it using pip:


```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install the package in editable mode
pip install -e .
```


### Verify Installation

After installation, verify that the CLI is available:

```bash
atc138 --help
```

You should see the command help output with available options.

## Running an Assessment

An assessment can be run directly from the command line, or as imported within a Python workflow. If `simulated_inputs.json` does not exist, it will be created using default inputs within `src/atc138/data`. Various assessment options can be overridden by placing them in file `optional_inputs.json` file within the input directory. This file can be customized for each assessment if desired and will be set as default values if not specified.

If `simulated_inputs.json` exists, the input builder will not re-run unless `--force_rebuild` is used in the CLI command.

### Running from the command line

With the input directory containing the necessary inputs, perform an assessment by running:

```bash
python -m atc138.cli dir/to/inputs dir/to/outputs [options]
```

Available options:
- `--seed SEED`: Random seed for reproducible results (integer)
- `--force_rebuild`: Force regeneration of `simulated_inputs.json` even if it exists

For example, the ICSB example case is run with:

```bash
python -m atc138.cli ./examples/ICSB ./examples/ICSB/output
```

Or with custom options:

```bash
python -m atc138.cli ./examples/ICSB ./examples/ICSB/output --seed 12345 --force_rebuild
```

### Imported via Python script

Once installed, the package can also be imported in scripts:

```python
from atc138 import driver

example_dir = './examples/ICSB'
output_dir = './examples/ICSB/output'

driver.run_analysis(example_dir, output_dir, seed=985)
```

If `simulated_inputs.json` exists, the input builder will not re-run unless the argument `force_rebuild=True` is used for `driver.run_analysis`.

### Plotting outputs

Several basic plotting tools are provided in `plotters/`, which can be used after an analysis generates results. This is run with

```python
from plotters.main_plot_functionality import plot_results
output_dir = './examples/ICSB/output'
plot_results(output_dir, p_gantt=50) # plot median realization
```

which will plot:
- Component and system-level breakdowns of hinderance to reoccupancy and functional status per day
- Distribution of realizations achieving reoccupancy and functional status per day
- Mean and per-realization breakdown of recovery trajectories
- Gantt chart of impeding factors, repair work, number of workers, and recovery status of building per day for the realization with  `p_gantt`-th percentile of functional recovery day. 

## Inputs
A brief description of the various input variables are provided below. A detailed schema of all expected input and output subfields is provided in [src/atc138/data/default_inputs.json](src/atc138/data/default_inputs.json).

### Example Inputs
Four example inputs are provided to help illustrate both the construction of the inputs file and the implementation. These files are located in the `examples/` directory and can be run through the assessment by setting the variable names accordingly above.

### Required Building Specific Data
Each file listed below contains data specific to the building performance model and simulated damage given for a specific level of shaking. Each file listed will need to be created for each unique assessment and saved in the root directory of the build script. Data are contained in either json  or csv format.
 - **building_model.json**: Basic properties of the building and performance model. Contains all variables within the _building_model_ structure defined in the inputs schema.
 - **tenant_unit_list.csv**: Table that lists each tenant unit within the building; one row per tenant unit. This table requires the following attributes:
     - id: [int or string] unique identifier for this tenant unit
     - story: [int] building story where this tenant unit is located (ground floor is listed at 1)
     - area: [number] total gross plan area of the tenant unit, in square feet
     - perim_area: [number] total exterior perimeter area (elevation) of the tenant unit, is square feet
     - occupancy_id: [int] foreign key to the _occupancy_id_ attribute of the tenant_function_requirements.csv table in the _data_ directory
 - **comp_ds_list.csv**: Table that lists each component and damage state populated in the building performance model; one row per each component's damage state. This table requires the following attributes:
     - comp_id: [string] unique FEMA P-58 component identifier
     - ds_seq_id: [int] interger index of the sequential parent damage state (i.e., damage state 1, 2, 3, 4);
     - ds_sub_id: [int] interger index for the mutually exlusive of simeltaneous sub damage state; use 1 to indicate a sequential damage state with no sub damage state.
 - **damage_consequences.json**: Building-level and story-level simulated properties of building damage. Contains all variables within the _damage_consequences_ structure defined in the inputs schema.
 - **simulated_damage.json**: Component-level simulated damage properties. Contains all variables within the _damage.tenant_units_ structure defined in the inputs schema. Each variable containing realization of component damage should be defined uniquely for each tenant unit (shown as "tu" below). Each tenant_unit cell should contain the following variables:
     - tenant_unit{tu}.qnt_damaged: [array: simulations × damage states] The number of damaged components in each component damage state for each realization of the simulation.
     - tenant_unit{tu}.worker_days: [array: simulations × damage states] The number of single worker days required to repair all damage to this damage state of this component at this story for each realization.
     - tenant_unit{tu}.qnt_damaged_side_1: [array: simulations × damage states] The number of damaged components in each component damage state assocaited with side 1 of the building; set to zero if not associated with a particular side. This is only for exterior cladding components.
     - tenant_unit{tu}.qnt_damaged_side_2: [array: simulations × damage states] The number of damaged components in each component damage state assocaited with side 2 of the building; set to zero if not associated with a particular side. This is only for exterior cladding components.
     - tenant_unit{tu}.qnt_damaged_side_3: [array: simulations × damage states] The number of damaged components in each component damage state assocaited with side 3 of the building; set to zero if not associated with a particular side. This is only for exterior cladding components.
     - tenant_unit{tu}.qnt_damaged_side_4: [array: simulations × damage states] The number of damaged components in each component damage state associated with side 4 of the building; set to zero if not associated with a particular side. This is only for exterior cladding components.
     - tenant_unit{tu}.num_comps: [array: 1 × damage states] The total number of components associated with each damage state (should be uniform for damage state of the same component stack).

### Additional Assessment Options
These options control various aspects of the functional recovery assessment and can be customized via `optional_inputs.json`. To customize assessment options, create an `optional_inputs.json` file in your input directory (can copy over from examples) with only the fields you want to override. Default analysis options are defined from [src/atc138/data/default_inputs.json](src/atc138/data/default_inputs.json)

- **impedance_options**: Python dictionary containing method inputs for assessing impeding factors (delays in starting repairs). Key fields include:
  - `include_impedance`: Enable/disable different delay types (inspection, financing, permitting, engineering, contractor)
  - `system_design_time`: Engineering design duration parameters (f, r, t, w for lognormal distribution)
  - `eng_design_min_days`/`eng_design_max_days`: Bounds on engineering design time
  - `mitigation`: Building-specific factors (essential facility status, contractor relationships, funding source)
  - `impedance_beta`: Uncertainty parameter for delay distributions
  - `default_lead_time`: Default procurement time for materials (182 days)
  - `demand_surge`: Regional demand surge effects based on urban density and ground motion

- **repair_time_options**: Python dictionary containing method inputs for the repair schedule. Key fields include:
  - `max_workers_per_sqft_story`: Maximum workers per square foot per story
  - `max_workers_per_sqft_story_temp_repair`: Maximum workers for temporary repairs
  - `max_workers_building_min`/`max_workers_building_max`: Bounds on total building workforce
  - `allow_tmp_repairs`: Enable/disable temporary repair capabilities
  - `allow_shoring`: Enable/disable shoring during repairs

- **functionality_options**: Python dictionary containing method inputs for building function assessment. Key fields include:
  - `calculate_red_tag`: Enable/disable red tag assessment
  - `red_tag_clear_time`: Days to clear red tags (default: 7)
  - `egress_threshold`: Minimum fraction of egress paths required (default: 0.5)
  - `fire_watch`: Enable/disable fire watch requirements
  - `habitability_requirements`: Utility requirements for habitability (electrical, water, HVAC)
  - `water_pressure_max_story`: Maximum stories affected by water pressure loss
  - `heat_utility`: Fuel type for heating ("gas" or "electric")
 
### Optional Building Specific Data
The file(s) listed below contain data that is optional for the assessment. If the files do not exist, the method will make simplifying assumptions to account for the missing data (as noted below). Save in the input directory of your analysis.
 - **utility_downtime.json**: Regional utility simulated downtimes for gas, water, and electrical power networks. Should contain arrays for each utility type with downtime in days per realization. If missing, assumes zero downtime for all utilities.

### Overriding Default Inputs

The assessment uses a hierarchy of input sources, with later sources taking precedence over earlier ones:

1. **Built-in defaults** from [src/atc138/data/default_inputs.json](src/atc138/data/default_inputs.json)
2. **Custom static tables** (CSV files copied to input directory)
3. **optional_inputs.json** (highest priority for assessment options)

### Customizing Static Tables

To override default component, system, or tenant attributes, copy the relevant CSV file from `src/atc138/data/` to your input directory and modify it:

- **component_attributes.csv**: Component properties (repair costs, crew sizes, system assignments)
- **damage_state_attribute_mapping.csv**: How damage states affect function and reoccupancy
- **systems.csv**: System definitions and functional requirements
- **subsystems.csv**: Subsystem groupings
- **tenant_function_requirements.csv**: Occupancy-specific functional thresholds
- **temp_repair_class.csv**: Temporary repair capabilities

For example, to modify component repair times, copy `component_attributes.csv` to your input directory and edit the relevant rows.

## Outputs
A brief description of the various output variables are provided below. A detailed schema of all expected input and output subfields is provided in [src/atc138/data/default_inputs.json](src/atc138/data/default_inputs.json).

 - **functionality['recovery']**: Python dictionary
   Python dictionary containing the simulated tenant- and building-level functional recovery and reoccupancy outcomes
 - **functionality['building_repair_schedule']**: Python dictionary
   Python dictionary containing the simulated building repair schedule
 - **functionality['worker_data']**: Python dictionary
   Python dictionary containing the simulation of allocated workers throughout the repair process
 - **functionality['impeding_factors']**: Python dictionary
   Python dictionary containing the simulated impeding factors delaying the start of system repair

## Building from Pelicun Outputs

Use this workflow when you have FEMA P-58 damage and loss results from Pelicun and want to assess functional recovery. This is an alternative to manually creating the raw input files described above.

**Requirements**: PBE Application version ~=4.4 and pelicun~=3.5 (optional dependency - install with `pip install pelicun~=3.5` if needed)

To use Pelicun outputs, ensure `simulated_inputs.json` does not exist in your model directory. Place the following Pelicun output files in your input directory:

### Required Pelicun Files
- **CMP_QNT.csv**: Component quantities and properties
- **DL_summary.csv**: Damage and loss summary (for irreparable cases)
- **DMG_sample.csv**: Damage realizations for all components
- **DV_repair_sample.csv**: Repair decision variables (legacy name `DV_bldg_repair_sample.csv` also supported)
- **general_inputs.json**: Building properties (egress, occupancy, dimensions, cost ratios)
- **input.json**: Basic building information (stories, replacement cost, plan area)

### Optional Pelicun Files
- **side_damage_ratio.csv**: Custom cladding damage distribution (num_reals × 2 array)

### Additional Required Files
- **tenant_unit_list.csv**: Tenant unit definitions (same format as manual workflow)

The assessment will automatically detect Pelicun files and convert them to the standard ATC-138 format. Use the same CLI or Python API as normal:

```python
from atc138 import driver

example_dir = './examples/RCSW_4story_pelicun'
output_dir = './examples/RCSW_4story_pelicun/output'

driver.run_analysis(example_dir, output_dir, seed=985)
```

**Note**: Cladding damage is currently distributed randomly across building sides. Custom side assignment is planned for future versions.

## Testing

Install the package with test dependencies:

```bash
pip install -e ".[test]"
```

Run the integration tests, which compare Python outputs against stored reference data for each model in `tests/fixtures/models/`:

```bash
pytest tests/test_integration.py -v
```

Integration tests are marked with `@pytest.mark.integration` and can be filtered:

```bash
# Run only integration tests
pytest -m integration

# Skip integration tests
pytest -m "not integration"
```

The comparison engine can also be used standalone for detailed inspection:

```bash
python tests/compare_runs.py <reference_dir> <python_output_dir>
```

### Validation Testing Against MATLAB

For detailed guidance on validating the Python implementation against the original MATLAB framework, see [tests/detailed_inspection_guide.md](tests/detailed_inspection_guide.md).
