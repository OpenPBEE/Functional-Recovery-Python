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
python -m atc138.cli dir/to/inputs dir/to/outputs
```

 For example, the ICSB example case is run with:

```bash
python -m atc138.cli ./examples/ICSB ./examples/ICSB/output
```

### Imported via Python script

Ensure that the `src/` directory is on the path of the main script. Then:

```python
from src.atc138 import driver

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

## Example Inputs
Four example inputs are provided to help illustrate both the construction of the inputs file and the implementation. These files are located in the `examples/` directory and can be run through the assessment by setting the variable names accordingly above.

## Definition of I/O
A brief description of the various input and output variables are provided below. A detailed schema of all expected input and output subfields is provided in the schema directory.

### Inputs
  - **impedance_options**: Python dictionary
   Python dictionary containing optional method inputs for the assessment of impeding factors
 - **repair_time_options**: Python dictionary
   Python dictionary containing optional method inputs for the assessment of the repair schedule
 - **functionality_options**: Python dictionary
   Python dictionary containing optional method inputs for the assessment of building function, such as functionality limit state thresholds
 - **building_model**: Python dictionary
   Python dictionary containing general information about the building such as the number of stories and the building area
 - **damage**: Python dictionary
   Python dictionary containing simulated damage, simulated repair time, and component attribute data associated with each component's damages state in the building
 - **damage_consequences**: Python dictionary
   Python dictionary containing simulated building consequences, such as red tags and repair costs ratios
 - **functionality['utilities']**: Python dictionary
   Python dictionary containing simulated utility downtimes
 - **tenant_units**: Python dictionary
   Python dictionary that contains the attributes and functional requirements of each tenant unit in the building

### Outputs
 - **functionality['recovery']**: Python dictionary
   Python dictionary containing the simulated tenant- and building-level functional recovery and reoccupancy outcomes
 - **functionality['building_repair_schedule']**: Python dictionary
   Python dictionary containing the simulated building repair schedule
 - **functionality['worker_data']**: Python dictionary
   Python dictionary containing the simulation of allocated workers throughout the repair process
 - **functionality['impeding_factors']**: Python dictionary
   Python dictionary containing the simulated impeding factors delaying the start of system repair

## Manually building the Inputs File
By default, the inputs file are built from a simpler set of building inputs, taking advantage of default assessment assumptions and component, system, and tenant attributes contained within the _data_ directory. If you would like to manually modify the data tables listed below for a specific model, simply copy the files to the input directory and modify them.

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

### Optional Building Specific Data
The file(s) listed below contain data that is optional for the assessment. If the files do not exist, the method will make simplifying assumptions to account for the missing data (as noted below). Save in the input directory of your analysis.
 - **utility_downtime.json**: Regional utility simulated downtimes for gas, water, and electrical power networks. Contains all variables within the _functionality['utilities']_ dictionary defined in the inputs schema.

### Default Optional Inputs
The Python file listed below defines additional assessment inputs based on set of default values. Place this file in the input directory of your analysis.
 - **optional_inputs.json**: Defines default variables for the impedance_options, repair_time_options, functionality_options, and regional_impact variables listed in the inputs schema.

<!-- How does a user modify the static tables (now data) without touching the original data files? -->

### Static Data
The csv tables listed below contain default component, damage state, system, and tenant function attributes that can be used to populate the required assessment inputs according to the methodology. These are located in the _data_ directory. To override the static data with custom versions, copy modified sheets and place them in the input directory.
 - **component_attributes.csv**: Attributes of components in the FEMA P-58 fragility database that are required for the functional recovery assessment.
 - **damage_state_attribute_mapping.csv**: Attributes of damage state in the FEMA P-58 fragility database and their affect on function and reoccupancy.
 - **subsystems.csv**: Attributes of each default subsystem considered in the method.
 - **tenant_function_requirements.csv**: Default tenant requirements for function for various occupancy classes.
 - **systems.csv**: Attributes of each default ssytem considered in the method.
 - **temp_repair_class.csv**: Attributes of each temprary repair class considered in the method.

## Building from Pelicun outputs
This conversion module is compatible with PBE Application version ~=4.4 and pelicun~=3.5. To build and rebuild raw ATC-138 input files from Pelicun outputs, ensure that simulated_inputs.json does not currently exist in the model directory. Then, the following Pelicun files are required as input:
 - **CMP_QNT.csv**: component sheet
 - **DL_summary.csv**: summary of damage and loss, to read in irreparable cases
 - **DMG_sample.csv**: damage sample of all realizations
 - **DV_repair_sample.csv**: decision variable sample of all realizations. The legacy name **DV_bldg_repair_sample.csv** is supported as a fallback name.
 - **general_inputs.json**: egress, occupancy, dimensions, ratio of engineering cost as a fraction of total repair cost. Number of elevators or stairs per story can also be explicitly specified here if it is desired to override the quantity in CMP_QNT.
 - **input.json**: JSON file with number of stories, replacement cost, plan area
 - **side_damage_ratio.csv** (optional): CSV of size num_reals x 2, specifies the damage distributed to each side for cladding components. This fraction is constant across the height of the building. Column 1 is the fraction of damaged components in direction 0, side 1. Column 2 is the fraction of damaged components in direction 1, side 1. These should sum up to 0.5. Parallel sides will have the same fraction of damage. If not provided, these ratios will be sampled uniformly for all realizations.

Additionally, the following inputs are required similar to the raw build procedure, but are not generated by Pelicun:
 - **tenant_unit_list.csv**

Then, the either the CLI or import method can be used to run the analysis as before, which will detect the presence of Pelicun files to use as build inputs. An example is provided in the model directory `RCSW_4story_pelicun`.

_Cladding damage:_ Current implementation of Pelicun inputs will randomly distribute the damage across 4 sides of the building for the purpose of cladding damage assignment. Custom side-assignment is planned for a future implementation.

```python
from src.atc138 import driver

example_dir = './examples/RCSW_4story_pelicun'
output_dir = './examples/RCSW_4story_pelicun/output'

driver.run_analysis(example_dir, output_dir, seed=985)
```

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
