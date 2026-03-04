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
