
import numpy as np
import json
import pandas as pd
import os
import re
import sys

def clean_types(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization,
    preserving NaN as float('nan') for Numpy compatibility in the engine.
    """
    if isinstance(obj, dict):
        return {k: clean_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_types(i) for i in obj]
    elif isinstance(obj, np.ndarray):
        return clean_types(obj.tolist())
    elif isinstance(obj, (np.int64, np.int32, int)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, float)):
         # Preserving NaN for numpy compatibility in downstream engine
         return float(obj)
    elif pd.isna(obj): 
        # Handle standalone pandas/numpy NaNs/NaTs
        return float('nan') 
    return obj

def recursive_update(d, u):
    """
    Recursively update dictionary d with values from u.
    """
    for k, v in u.items():
        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
            recursive_update(d[k], v)
        else:
            d[k] = v
    return d

def load_custom_static_tables(model_dir, static_dir, filename):
    '''
    Safely loads static tables if custom versions are found in model directory

    Parameters
    ----------
    model_dir: string
        Path to the directory containing raw input files.

    static_dir: string
        Path to the original default static tables

    filename: string
        Name of static table
    '''
    
    path = os.path.join(model_dir, filename)
    if os.path.exists(path):
        print(f"found custom {filename} in inputs. Overriding static tables...")
    else:
        path = os.path.join(static_dir, filename)
    return pd.read_csv(path)


def build_simulated_inputs(model_dir):
    """
    Generates simulated_inputs dictionary from raw input files in the model directory.
    Based on the original build_inputs.py script.
    
    Parameters
    ----------
    model_dir: string
        Path to the directory containing raw input files.
        
    Returns
    -------
    simulated_inputs: dict
        The complete dictionary of inputs.
    """
        
    ''' PULL STATIC DATA
    If static data tables exist in the input directory, use those. Else, use
    the defaults in src/atc138/data/
    '''
    
    static_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    component_attributes = load_custom_static_tables(
        model_dir, static_data_dir, 'component_attributes.csv')

    damage_state_attribute_mapping = load_custom_static_tables(
        model_dir, static_data_dir, 'damage_state_attribute_mapping.csv')

    subsystems = load_custom_static_tables(
        model_dir, static_data_dir, 'subsystems.csv')

    tenant_function_requirements = load_custom_static_tables(
        model_dir, static_data_dir, 'tenant_function_requirements.csv')
    
    '''LOOK FOR RAW INPUTS
    If Pelicun files exist, build from there
    '''
    pelicun_path = os.path.join(model_dir, 'DMG_sample.csv')
    if os.path.exists(pelicun_path):
        print(f"Pelicun outputs found in {model_dir}. Attempting build...")
        convert_pelicun(model_dir)
    
    
    ''' LOAD BUILDING DATA
    This data is specific to the building model and will need to be created
    for each assessment. Data is formated as json structures or csv tables'''
    
    # 1. Building Model: Basic data about the building being assessed
    with open(os.path.join(model_dir, 'building_model.json'), 'r') as f:
        building_model = json.load(f)
    
    # If number of stories is 1, change individual values to lists in order to work with later code
    if building_model['num_stories'] == 1:
        for key in ['area_per_story_sf', 'ht_per_story_ft', 'occupants_per_story', 'stairs_per_story', 'struct_bay_area_per_story']:
            if not isinstance(building_model[key], list):
                building_model[key] = [building_model[key]]
    if building_model['num_stories'] == 1:
        for key in ['edge_lengths']:
            if not isinstance(building_model[key][0], list):
                building_model[key] = [[building_model[key][0]], [building_model[key][1]]]
    
    # 2. List of tenant units within the building and their basic attributes
    tenant_unit_list = pd.read_csv(os.path.join(model_dir, 'tenant_unit_list.csv'))
    
    
    # 3. List of component and damage states ids associated with the damage
    comp_ds_list = pd.read_csv(os.path.join(model_dir, 'comp_ds_list.csv'))
    
    # 4. List of component and damage states in the performance model
    comp_population = pd.read_csv(os.path.join(model_dir, 'comp_population.csv'))
    comp_header = list(comp_population.columns)
    comp_list = np.array(comp_header[2:len(comp_header)])
    comp_list= np.char.replace(np.array(comp_list),'_','.')
    comp_list = comp_list.tolist()
    # Remove suffixes from repated entries
    for i in range(len(comp_list)):
        if len(comp_list[i]) > 10:
            comp_list[i]=comp_list[i][0:10]
    building_model['comps'] = {'comp_list' : comp_list} #FZ# Component list has been added to building model dictionary.
    
    # Go through each story and assign component populations
    drs = np.unique(np.array(comp_population['dir']))
    
    building_model['comps']['story'] = {}
    for s in range (building_model['num_stories']):
        building_model['comps']['story'][s] = {}
        for d in range(len(drs)):
            # [FIX] Robust key generation and missing data handling
            current_dir = drs[d]
            filt = np.logical_and(np.array(comp_population['story']) == s+1, np.array(comp_population['dir']) == current_dir)
            
            # Format key identifier using integer representation of direction to ensure consistency (e.g. qty_dir_1 not qty_dir_1.0)
            try:
                dir_key_suffix = str(int(current_dir))
            except:
                dir_key_suffix = str(current_dir)
            
            qty_data = comp_population.to_numpy()[filt,2:len(comp_header)]
            
            if qty_data.shape[0] > 0:
                building_model['comps']['story'][s]['qty_dir_' + dir_key_suffix] = qty_data.tolist()[0]
            else:
                # Missing data for this story/direction, fill with zeros to avoid crashes
                num_comps = len(comp_header) - 2
                building_model['comps']['story'][s]['qty_dir_' + dir_key_suffix] = [0] * num_comps
    
    
    # Set comp info table
    comp_info = {'comp_id': [], 'comp_idx': [], 'structural_system': [], 'structural_system_alt': [], 'structural_series_id': []}
    for c in range(len(comp_list)):
        # Find the component attributes of this component
        comp_attr_filt = component_attributes['fragility_id'] == comp_list[c]
        if np.logical_not(sum(comp_attr_filt) == 1):
            sys.exit('error!.Could not find component attrubutes')
        else:
            comp_attr = component_attributes.to_numpy()[comp_attr_filt,:]
        comp_info['comp_id'].append(comp_list[c])
        comp_info['comp_idx'].append(c) 
        
        # [FIX] Scalar extraction: Use scalar indexing [0, col] instead of slicing [0, [col]] to avoid array-to-scalar conversion errors
        comp_info['structural_system'].append(float(comp_attr[0, component_attributes.columns.get_loc('structural_system')]))
        comp_info['structural_system_alt'].append(float(comp_attr[0, component_attributes.columns.get_loc('structural_system_alt')]))
        comp_info['structural_series_id'].append(float(comp_attr[0, component_attributes.columns.get_loc('structural_series_id')]))
    
    building_model['comps']['comp_table'] = comp_info
    
    
    ''' LOAD SIMULATED DATA
    This data is specific to the building performance at the assessed hazard intensity 
    and will need to be created for each assessment. 
    Data is formated as json structures.'''
    
    # 1. Simulated damage consequences - various building and story level consequences of simulated data, for each realization of the monte carlo simulation.
    with open(os.path.join(model_dir, 'damage_consequences.json'), 'r') as f:
        damage_consequences = json.load(f)
    
    # 2. Simulated utility downtimes for electrical, water, and gas networks for each realization of the monte carlo simulation.
    # If file exists load it 
    utility_path = os.path.join(model_dir, 'utility_downtime.json')
    if os.path.exists(utility_path):
        with open(utility_path, 'r') as f:
            functionality = json.load(f)
    # else If no data exist, assume there is no consequence of network downtime
    else:
        num_reals = len(damage_consequences["repair_cost_ratio_total"])
        functionality = {'utilities' : {'electrical':[], 'water':[], 'gas':[]} } 
    
        for real in range(num_reals):
            functionality['utilities']['electrical'].append(0)
            functionality['utilities']['water'].append(0)
            functionality['utilities']['gas'].append(0)
    
    
    # 3. Simulated component damage per tenant unit for each realization of the monte carlo simulation
    # 3. Simulated component damage per tenant unit for each realization of the monte carlo simulation
    with open(os.path.join(model_dir, 'simulated_damage.json'), 'r') as f:
        sim_damage = json.load(f)
    
    # Write in individual dictionaries part of larger 'damage' dictionary 
    damage = {'story' : {}, 'tenant_units' : {}}
    
    if 'tenant_units' in list(sim_damage.keys()):
        for tu in range(len(sim_damage['tenant_units'])):
            damage['tenant_units'][tu] = sim_damage['tenant_units'][tu]
    
    
    if 'story' in list(sim_damage.keys()):
        for s in range(len(sim_damage['story'])):
            damage['story'][s] = sim_damage['story'][s]
        
    ''' OPTIONAL INPUTS
    Various assessment otpions. Set to default options in the
    optional_inputs.json file. This file is expected to be in this input
    directory. This file can be customized for each assessment if desired.'''
    
    # Load defaults first, then merge user overrides
    pkg_dir = os.path.dirname(__file__)
    defaults_path = os.path.join(pkg_dir, 'data', 'default_inputs.json')
    with open(defaults_path, 'r') as f:
        options = json.load(f)

    user_options_path = os.path.join(model_dir, 'optional_inputs.json')
    if os.path.exists(user_options_path):
        with open(user_options_path, 'r') as f:
            user_options = json.load(f)
        options = recursive_update(options, user_options)
        
    functionality_options = options['functionality_options']
    impedance_options = options['impedance_options']
    repair_time_options = options['repair_time_options']

 
    
    # Preallocate tenant unit table
    tenant_units = tenant_unit_list.copy() # copy to avoid SettingWithCopy if passed dataframe
    tenant_units['exterior'] = np.zeros(len(tenant_units))
    tenant_units['interior'] = np.zeros(len(tenant_units))
    tenant_units['occ_per_elev'] = np.zeros(len(tenant_units))
    tenant_units['is_elevator_required'] = np.zeros(len(tenant_units))
    tenant_units['is_electrical_required'] = np.zeros(len(tenant_units))
    tenant_units['is_water_potable_required'] = np.zeros(len(tenant_units))
    tenant_units['is_water_sanitary_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_ventilation_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_heating_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_cooling_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_exhaust_required'] = np.zeros(len(tenant_units))
    tenant_units['is_data_required'] = np.zeros(len(tenant_units))  
    '''Pull default tenant unit attributes for each tenant unit listed in the
    tenant_unit_list'''
    for tu in range(len(tenant_unit_list)):
        occ_id = tenant_units.loc[tu, 'occupancy_id'] # Use .loc for pandas safety
        fnc_requirements_filt = tenant_function_requirements['occupancy_id'] == occ_id
        if sum(fnc_requirements_filt) != 1:
            raise ValueError(f'error! Tenant Unit Requirements for Occupancy ID {occ_id} Not Found')
        
        # Accessing filtered rows. Original input builder used filtered Series assignment.
        req_row = tenant_function_requirements[fnc_requirements_filt].iloc[0]
        
        tenant_units.loc[tu, 'exterior'] = req_row['exterior']
        tenant_units.loc[tu, 'interior'] = req_row['interior']
        tenant_units.loc[tu, 'occ_per_elev'] = req_row['occ_per_elev']
        
        story = tenant_units.loc[tu, 'story']
        if req_row['is_elevator_required'] == 1 and req_row['max_walkable_story'] < story:
            tenant_units.loc[tu, 'is_elevator_required'] = 1
        else:
            tenant_units.loc[tu, 'is_elevator_required'] = 0
    
        tenant_units.loc[tu, 'is_electrical_required'] = req_row['is_electrical_required']
        tenant_units.loc[tu, 'is_water_potable_required'] = req_row['is_water_potable_required']
        tenant_units.loc[tu, 'is_water_sanitary_required'] = req_row['is_water_sanitary_required']
        tenant_units.loc[tu, 'is_hvac_ventilation_required'] = req_row['is_hvac_ventilation_required']
        tenant_units.loc[tu, 'is_hvac_heating_required'] = req_row['is_hvac_heating_required']
        tenant_units.loc[tu, 'is_hvac_cooling_required'] = req_row['is_hvac_cooling_required']
        tenant_units.loc[tu, 'is_hvac_exhaust_required'] = req_row['is_hvac_exhaust_required']
        tenant_units.loc[tu, 'is_data_required'] = req_row['is_data_required']    
    '''Pull default component and damage state attributes for each component 
    in the comp_ds_list'''
    
    ## Populate data for each damage state
    comp_ds_info = {'comp_id' : [], 
                    'comp_type_id' : [], 
                    'comp_idx' : [], 
                    'ds_seq_id' : [], 
                    'ds_sub_id' : [],
                    'system' : [],
                    'subsystem_id' : [],
                    'structural_system' : [],
                    'structural_system_alt' : [],
                    'structural_series_id' : [],
                    'unit' : [],
                    'unit_qty' : [],
                    'service_location' : [],
                    'is_sim_ds' : [],
                    'safety_class' : [],
                    'affects_envelope_safety' : [],
                    'ext_falling_hazard' : [],
                    'int_falling_hazard' : [],
                    'global_hazardous_material' : [],
                    'local_hazardous_material' : [],
                    'weakens_fire_break' : [],
                    'affects_access' : [],
                    'damages_envelope_seal' : [],
                    'affects_roof_function' : [],
                    'obstructs_interior_space' : [],
                    'impairs_system_operation' : [],
                    'causes_flooding' : [],
                    'interior_area_factor' : [],
                    'interior_area_conversion_type' : [],
                    'exterior_surface_area_factor' : [],
                    'exterior_falling_length_factor' : [],
                    'crew_size' : [],
                    'permit_type' : [],
                    'redesign' : [],
                    'long_lead_time' : [],
                    'requires_shoring' : [],
                    'resolved_by_scaffolding' : [],
                    'tmp_repair_class' : [],
                    'tmp_repair_time_lower' : [],
                    'tmp_repair_time_upper' : [],
                    'tmp_repair_time_lower_qnty' : [],
                    'tmp_repair_time_upper_qnty' : [],
                    'tmp_crew_size' : [],
                    'n1_redundancy' : [],
                    'parallel_operation' :[],
                    'redundancy_threshold' : []
                    }
    
    for c in range(len(comp_ds_list)):
        
        # Find the component attributes of this component
        comp_attr_filt = component_attributes['fragility_id'] == comp_ds_list['comp_id'][c]
        if sum(comp_attr_filt) != 1:
            raise ValueError('error! Could not find component attrubutes')
        else:
            comp_attr = component_attributes[comp_attr_filt].iloc[0] # Changed to Series access for robust scalar extraction
                  
        ds_comp_filt = []
        for frag_reg in range(len(damage_state_attribute_mapping["fragility_id_regex"])):
            regex_str = damage_state_attribute_mapping["fragility_id_regex"][frag_reg]
            cid = comp_ds_list["comp_id"][c]
            match = re.search(regex_str, cid)
            

            # Mapping components with attributes - Cjecks are based on mapping, comp_id, seq_id and sub_id

            # Matching element ID using information contained in damage_state_attribute_mapping ["fragility_id_regex"]
            if match and match.string == cid:
                ds_comp_filt.append(True)
            else:
                ds_comp_filt.append(False)    
        
        ds_comp_filt = np.array(ds_comp_filt) # Convert to array for boolean indexing

        ds_seq_filt = damage_state_attribute_mapping['ds_index'] == comp_ds_list['ds_seq_id'][c]
        if comp_ds_list['ds_sub_id'][c] == 1:
            ds_sub_filt = np.logical_or(damage_state_attribute_mapping['sub_ds_index'] ==1, damage_state_attribute_mapping['sub_ds_index'].isnull())
        else:
            ds_sub_filt = damage_state_attribute_mapping['sub_ds_index'] == comp_ds_list['ds_sub_id'][c]
        
        ds_filt = ds_comp_filt & ds_seq_filt & ds_sub_filt
        
        if sum(ds_filt) != 1:
             raise ValueError('error!, Could not find damage state attrubutes')
        else:
            ds_attr = damage_state_attribute_mapping[ds_filt].iloc[0] # Series access
        
        ## Populate data for each damage state
        # Basic Component and DS identifiers
        comp_ds_info['comp_id'].append(comp_ds_list['comp_id'][c])
        comp_ds_info['comp_type_id'].append(comp_ds_list['comp_id'][c][0:5]) # first 5 characters indicate the type
        comp_ds_info['comp_idx'].append(c)
        comp_ds_info['ds_seq_id'].append(ds_attr['ds_index'])
        
        sub_id = ds_attr['sub_ds_index']
        if pd.isna(sub_id): sub_id = 1.0
        comp_ds_info['ds_sub_id'].append(sub_id)
            
        # Set Component Attributes
        comp_ds_info['system'].append(comp_attr['system_id'])
        comp_ds_info['subsystem_id'].append(comp_attr['subsystem_id'])
        comp_ds_info['structural_system'].append(comp_attr['structural_system'])
        comp_ds_info['structural_system_alt'].append(comp_attr['structural_system_alt']) # component_attributes.csv does not have structural_system_alt field
        comp_ds_info['structural_series_id'].append(comp_attr['structural_series_id'])
        comp_ds_info['unit'].append(comp_attr['unit']) #FZ# Check w.r.t. matlab output
        comp_ds_info['unit_qty'].append(comp_attr['unit_qty'])
        comp_ds_info['service_location'].append(comp_attr['service_location']) #FZ# Check w.r.t. matlab output
                   
        # Set Damage State Attributes
        # Map fields (legacy mapping logic preserved where simple)
        comp_ds_info['is_sim_ds'].append(ds_attr['is_sim_ds'])
        comp_ds_info['safety_class'].append(ds_attr['safety_class'])
        comp_ds_info['affects_envelope_safety'].append(ds_attr['affects_envelope_safety'])
        comp_ds_info['ext_falling_hazard'].append(ds_attr['exterior_falling_hazard'])
        comp_ds_info['int_falling_hazard'].append(ds_attr['interior_falling_hazard'])
        comp_ds_info['global_hazardous_material'].append(ds_attr['global_hazardous_material'])
        comp_ds_info['local_hazardous_material'].append(ds_attr['local_hazardous_material'])
        comp_ds_info['weakens_fire_break'].append(ds_attr['weakens_fire_break'])
        comp_ds_info['affects_access'].append(ds_attr['affects_access'])
        comp_ds_info['damages_envelope_seal'].append(ds_attr['damages_envelope_seal'])
        comp_ds_info['affects_roof_function'].append(ds_attr['affects_roof_function'])
        comp_ds_info['obstructs_interior_space'].append(ds_attr['obstructs_interior_space'])
        comp_ds_info['impairs_system_operation'].append(ds_attr['impairs_system_operation'])
        comp_ds_info['causes_flooding'].append(ds_attr['causes_flooding'])
        comp_ds_info['interior_area_factor'].append(ds_attr['interior_area_factor'])
        comp_ds_info['interior_area_conversion_type'].append(ds_attr['interior_area_conversion_type'])    
        comp_ds_info['exterior_surface_area_factor'].append(ds_attr['exterior_surface_area_factor'])
        comp_ds_info['exterior_falling_length_factor'].append(ds_attr['exterior_falling_length_factor'])                
        comp_ds_info['crew_size'].append(ds_attr['crew_size'])
        comp_ds_info['permit_type'].append(ds_attr['permit_type'])
        comp_ds_info['redesign'].append(ds_attr['redesign'])
        comp_ds_info['long_lead_time'].append(impedance_options['default_lead_time'] * ds_attr['long_lead'])
        comp_ds_info['requires_shoring'].append(ds_attr['requires_shoring'])
        comp_ds_info['resolved_by_scaffolding'].append(ds_attr['resolved_by_scaffolding'])
        comp_ds_info['tmp_repair_class'].append(ds_attr['tmp_repair_class'])
        comp_ds_info['tmp_repair_time_lower'].append(ds_attr['tmp_repair_time_lower'])
        comp_ds_info['tmp_repair_time_upper'].append(ds_attr['tmp_repair_time_upper'])
        
        tmp_class = ds_attr['tmp_repair_class']
        if tmp_class > 0:
            comp_ds_info['tmp_repair_time_lower_qnty'].append(ds_attr['time_lower_quantity'])
            comp_ds_info['tmp_repair_time_upper_qnty'].append(ds_attr['time_upper_quantity'])
        else:
            comp_ds_info['tmp_repair_time_lower_qnty'].append(np.nan)
            comp_ds_info['tmp_repair_time_upper_qnty'].append(np.nan)
    
        comp_ds_info['tmp_crew_size'].append(ds_attr['tmp_crew_size'])
    
        # Subsystem attributes
        sub_id = comp_attr['subsystem_id']
        subsystem_filt = subsystems['id'] == sub_id
        if sub_id == 0:
            # No subsytem
            comp_ds_info['n1_redundancy'].append(0)
            comp_ds_info['parallel_operation'].append(0)
            comp_ds_info['redundancy_threshold'].append(0)
        elif sum(subsystem_filt) != 1:
            sys.exit('error! Could not find damage state attrubutes')
        else:
            sub_row = subsystems[subsystem_filt].iloc[0]
            comp_ds_info['n1_redundancy'].append(sub_row['n1_redundancy'])
            comp_ds_info['parallel_operation'].append(sub_row['parallel_operation'])
            comp_ds_info['redundancy_threshold'].append(sub_row['redundancy_threshold'])
    
    damage['comp_ds_table'] = comp_ds_info
    
    ## Check missing data
    # Engineering Repair Cost Ratio - Assume is the sum of all component repair
    # costs that require redesign
    ## Check missing data
    # Engineering Repair Cost Ratio - Assume is the sum of all component repair
    # costs that require redesign
    if 'repair_cost_ratio_engineering' not in damage_consequences:
        eng_filt = np.array(damage['comp_ds_table']['redesign']).astype(bool)
        # Re-calc using numpy arrays
        costs = np.zeros(len(damage_consequences['repair_cost_ratio_total']))
        if 'story' in sim_damage:
             for s in range(len(sim_damage['story'])):
                 story_costs = np.array(sim_damage['story'][s]['repair_cost'])
                 costs += np.sum(story_costs[:, eng_filt], axis=1)
        damage_consequences['repair_cost_ratio_engineering'] = costs.tolist()
    

    # Convert tenant_units dataframe to dictionary
    tenant_units_dict = tenant_units.to_dict(orient='list')
         
    # Export output as simulated_inputs.json file 
    
    simulated_inputs = {'building_model' : building_model, 'damage' : damage, 'damage_consequences' : damage_consequences, 'functionality' : functionality, 'functionality_options' : functionality_options, 'impedance_options' : impedance_options, 'repair_time_options' : repair_time_options, 'tenant_units' : tenant_units_dict}
    
    # [FIX] Type cleaning using recursive helper (enables JSON serialization while preserving NaNs)
    simulated_inputs = clean_types(simulated_inputs)
    
    return simulated_inputs

def save_json(data, path):
    '''util to save json'''
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# SI conversion factors for units relevant to FEMA P-58 components.
# To convert from unit_a to unit_b: value_b = value_a * (factor_a / factor_b)
_UNIT_TO_SI = {
    # Area (to m²)
    'sf': 0.09290304, 'SF': 0.09290304, 'ft2': 0.09290304, 'm2': 1.0,
    # Length (to m)
    'lf': 0.3048, 'LF': 0.3048, 'ft': 0.3048, 'm': 1.0,
    # Count (unitless)
    'ea': 1.0, 'EA': 1.0, 'each': 1.0,
}


def _pelicun_to_p58_factor(pelicun_unit, atc138_unit, unit_qty):
    """Compute factor to convert a Pelicun physical quantity to P-58 unit count.

    value_in_p58_units = value_from_pelicun * factor

    When both units belong to the same physical dimension (area, length, or
    count), the factor converts between unit systems and then divides by the
    P-58 block size (unit_qty).  When the dimensions are incompatible (e.g.
    Pelicun reports EA but ATC-138 expects amp/ton/cfm), the Pelicun value
    is assumed to already represent a P-58 unit count and the factor is 1.0.
    """
    p_si = _UNIT_TO_SI.get(pelicun_unit)
    a_si = _UNIT_TO_SI.get(atc138_unit)
    if p_si is not None and a_si is not None:
        return (p_si / a_si) / unit_qty
    return 1.0


def clean_frag_id(frag_id: str) -> str:
    """
    Splits by ".", 
    returns string up until last period + "." + string after last period
    
    e.g. to convert from B.10.10.100a to B1010.100a
    """
    parts = frag_id.split('.')
    return '.'.join(["".join(parts[:-1]), parts[-1]])

def reorder_dv_cols(df, dv_tag_meta, ordered_tags=("dmg","loc","dir","ds")):
    """
    Rename columns from dv-loss-dmg-ds-loc-dir -> dmg-loc-dir-ds.

    Parameters
    ----------
    df : pandas.DataFrame
    dv_tag_meta : list[str]
        Order of tags in the column names.
    ordered_tags : tuple[str]
        Tags to retain in output column names.

    Returns
    -------
    pandas.DataFrame
        DataFrame with renamed columns.
    """
    keep_idx = [dv_tag_meta.index(k) for k in ordered_tags]

    new_cols = []
    for col in df.columns:
        parts = col.split("-")
        if len(parts) == len(dv_tag_meta):
            new_cols.append("-".join(parts[i] for i in keep_idx))
        else:
            new_cols.append(col)

    df.columns = new_cols
    return df

def story_mask(location, num_stories):
    """Translate story selection"""
    stories = np.arange(1, num_stories + 1)

    if location == "all":
        return np.ones(num_stories, dtype=bool)

    if location == "roof":
        mask = np.zeros(num_stories, dtype=bool)
        mask[-1] = True
        return mask
    
    # HP: temporary fix, have an alias for roof as top
    if location == "top":
        mask = np.zeros(num_stories, dtype=bool)
        mask[-1] = True
        return mask

    if "--" in location:
        start, end = map(int, location.split("--"))
        return (stories >= start) & (stories <= end)

    if ',' in location:
        loc_vec = np.array(location.split(','), dtype=int)
        return np.isin(stories, loc_vec)

    loc_vec = np.array(location.split(), dtype=int)
    return np.isin(stories, loc_vec)

def convert_pelicun(model_dir):
    '''
    Function to load in Pelicun files
    
    Requirements:
        - CMP_QNT.csv: component sheet
        - DL_summary.csv: summary of damage and loss, to read in irreparable cases
        - DMG_sample.csv: damage sample of all realizations
        - DV_repair_sample.csv: decision variable sample of all realizations
        - general_inputs.json: egress, occupancy, dimensions
        - input.json: JSON file with number of stories, replacement cost, plan area
    '''

    from copy import deepcopy

    with open(os.path.join(model_dir, 'input.json')) as file:
        pelicun_inputs = json.load(file)  

    ############ Pull basic model info from Pelicun Inputs
    num_stories = int(pelicun_inputs['DL']['Asset']['NumberOfStories'])
    if 'Repair' in pelicun_inputs['DL']['Losses']:
        total_cost = float(pelicun_inputs['DL']['Losses']['Repair']['ReplacementCost']['Median'])
    else:
        total_cost = float(pelicun_inputs['DL']['Losses']['BldgRepair']['ReplacementCost']['Median'])
    plan_area = float(pelicun_inputs['DL']['Asset']['PlanArea'])

    ########### Load Pelicun files
    # pull components 
    comps = pd.read_csv(os.path.join(model_dir, 'CMP_QNT.csv'))

    # repair cost realizations
    DV_summary = pd.read_csv(os.path.join(model_dir, 'DL_summary.csv'))

    # damage realizations
    damage = pd.read_csv(os.path.join(model_dir, 'DMG_sample.csv'))

    # decision variables
    if os.path.exists(os.path.join(model_dir, "DV_repair_sample.csv")):
        dvs = pd.read_csv(os.path.join(model_dir, "DV_repair_sample.csv"))
    else:
        dvs = pd.read_csv(os.path.join(model_dir, "DV_bldg_repair_sample.csv"))

    # siding damage ratio
    if os.path.exists(os.path.join(model_dir, "side_damage_ratio.csv")):
        ratio_damage_per_side = np.loadtxt(
            os.path.join(model_dir, "side_damage_ratio.csv"), delimiter=',')
    else:
        ratio_damage_per_side = None

    # ds attributes
    static_data_dir = os.path.join(os.path.dirname(__file__), 'data')
    ds_attributes = load_custom_static_tables(model_dir, static_data_dir, 'damage_state_attribute_mapping.csv')
    component_attributes = load_custom_static_tables(
        model_dir, static_data_dir, 'component_attributes.csv')

    # general inputs
    with open(os.path.join(model_dir, 'general_inputs.json')) as file:
        general_inputs = json.load(file)

    # remove Units row (case insensitive)
    # the first column is the cmp-loc-dir-ds or dv-loss-dmg-ds-loc-dir indicator
    damage = damage[~damage.iloc[:,0].astype(str).str.lower().str.contains('unit')]
    dvs = dvs[~dvs.iloc[:,0].astype(str).str.lower().str.contains('unit')]

    # Get meta-naming convention, then filter to just cmp columns
    # (case insensitive)
    tag_name_list = damage.columns[0].lower().split('-')
    frag_cols = damage.columns[
        damage.columns.str.match(r"^[B-F]")
    ]
    damage = damage[frag_cols]

    # damage column convention: cmp-loc-dir-ds, B.10.44.101-1-2-1
    # DV column convention:  dv-loss-dmg-ds-loc-dir, Cost-B.10.44.101-B.10.44.101-1-1-2

    # Filter DV columns
    dv_tag_meta = dvs.columns[0].lower().split('-')
    DV_time = dvs.loc[:, dvs.columns.str.upper().str.startswith("TIME")]
    DV_cost = dvs.loc[:, dvs.columns.str.upper().str.startswith("COST")]

    # reformat dv columns to cmp-loc-dir-ds
    DV_cost = reorder_dv_cols(DV_cost, dv_tag_meta)
    DV_time = reorder_dv_cols(DV_time, dv_tag_meta)

    ########### building_model.json

    # if stairs_per_story is not provided, calculate from CMP_QNT
    if 'stairs_per_story' not in general_inputs:
        # count number of stairs in the building
        stair_mask = comps["ID"].str.contains("C.20.11", regex=False)
        # Assumes number of vertical egress routes is the min number of stairs on any story. This is faulty logic and wont hold true for all comp tables 
        num_stairs = comps.loc[stair_mask, "Theta_0"].min() if stair_mask.any() else 0
        stairs_per_story = [int(num_stairs)] * num_stories
    else:
        stairs_per_story = general_inputs['stairs_per_story']

    # if num_elevators is not provided, calculate from CMP_QNT
    if 'num_elevators' not in general_inputs:
        # Count the number of elevator bays in the building
        # HP: should there be an override for this (manual elevator specification not in CMP list)
        elev_mask = comps["ID"].str.contains("D.10.14", regex=False)
        num_elev = comps.loc[elev_mask, "Theta_0"].max() if elev_mask.any() else 0
    else:
        num_elev = general_inputs['num_elevators']

    # construct building_model.json
    building_model = dict(
        building_value=total_cost,
        num_stories=num_stories,
        area_per_story_sf=[plan_area] * num_stories,
        ht_per_story_ft=[general_inputs["typ_story_ht_ft"]] * num_stories,
        edge_lengths=[
            [general_inputs["length_side_1_ft"]] * num_stories,
            [general_inputs["length_side_2_ft"]] * num_stories,
        ],
        struct_bay_area_per_story=[
            general_inputs["typ_struct_bay_area_ft"]
        ] * num_stories,
        num_entry_doors=general_inputs["num_entry_doors"],
        num_elevators=int(num_elev),
        stairs_per_story=stairs_per_story,
        occupants_per_story=[
            general_inputs["peak_occ_rate"] * plan_area
        ] * num_stories,
    )

    save_json(building_model, os.path.join(model_dir, "building_model.json"))


    ################ construct damage_consequences.json

    # determine replacement cases
    replacement_mask = DV_summary["collapse"].astype('int') | DV_summary["irreparable"].astype('int')

    # calculate repair cost ratio
    # HP: check nomenclature "-" vs "_"

    # HP: missing racked stair doors per story, racked entry doors

    if 'engineering_cost_ratio' not in general_inputs:
        eng_cost_ratio = 0.10
    else:
        eng_cost_ratio = general_inputs['engineering_cost_ratio']

    # Convert Pelicun worker-days to calendar days for replacement time.
    # Use the same max-workers formula as the repair scheduler, but
    # cap the effective area at a limited number of parallel floors to consider
    # that construction proceeds upward — a 40-story building will not have all
    # floors staffed simultaneously.
    _MAX_PARALLEL_FLOORS = 6
    _default_rto = json.load(
        open(os.path.join(static_data_dir, 'default_inputs.json'))
    )['repair_time_options']
    _wkr_per_sf = _default_rto['max_workers_per_sqft_building']
    _wkr_min = _default_rto['max_workers_building_min']
    _wkr_max = _default_rto['max_workers_building_max']

    _effective_floors = min(num_stories, _MAX_PARALLEL_FLOORS)
    _effective_area = _effective_floors * plan_area
    _max_workers = min(
        max(int(_effective_area * _wkr_per_sf + 10), _wkr_min),
        _wkr_max,
    )
    _replacement_time_days = np.where(
        replacement_mask,
        DV_summary["repair_time-parallel"] / _max_workers,
        np.nan,
    )

    damage_consequences = dict(
        repair_cost_ratio_total=(
            DV_summary["repair_cost-"] / total_cost
        ).tolist(),
        repair_cost_ratio_engineering=(
            DV_summary["repair_cost-"] / total_cost * eng_cost_ratio
        ).tolist(),
        simulated_replacement_time=_replacement_time_days.tolist(),
    )

    save_json(
        damage_consequences,
        os.path.join(model_dir, "damage_consequences.json"),
    )

    ############### build comp_ds_list.csv

    # Unique components + clean frag_id
    unique_frags = (
        comps["ID"]
        .dropna()
        .unique()
    )

    frag_df = pd.DataFrame({
        "comp_id": [clean_frag_id(f) for f in unique_frags]
    })

    # Cross-match using regex found in static table
    rows = []

    for _, frag_row in frag_df.iterrows():

        frag_id = frag_row["comp_id"]

        #  regex match
        matches = ds_attributes[
            ds_attributes["fragility_id_regex"]
            .apply(lambda pat: bool(pd.notna(pat) and re.search(pat, frag_id)))
        ]

        if matches.empty:
            continue

        # Build rows in one go
        temp = matches[["ds_index", "sub_ds_index"]].copy()
        temp["comp_id"] = frag_id

        rows.append(temp)

    if not rows:
        comp_ds_list = pd.DataFrame(
            columns=["comp_id", "ds_seq_id", "ds_sub_id"]
        )
    else:
        comp_ds_list = pd.concat(rows, ignore_index=True)

        # Clean sub_ds_index
        comp_ds_list["ds_sub_id"] = (
            comp_ds_list["sub_ds_index"]
            .replace(np.nan, 1)
            .astype(float)
            .astype(int)
        )

        comp_ds_list = comp_ds_list.rename(
            columns={"ds_index": "ds_seq_id"}
        )[["comp_id", "ds_seq_id", "ds_sub_id"]]

    # Save
    output_path = os.path.join(model_dir, "comp_ds_list.csv")
    comp_ds_list.to_csv(output_path, index=False)


    ################# construct comp_population.csv

    # list of stories and directions
    stories = np.arange(1, num_stories + 1)
    dirs = np.array([1, 2, 3])

    # handle multi index
    multi_index = pd.MultiIndex.from_product(
        [stories, dirs],
        names=["story", "dir"]
    )

    comp_population = pd.DataFrame(index=multi_index)

    # build comp_population.csv

    # restrict components to only those validated in comp_ds_list
    comps['tmp_clean_id'] = comps['ID'].apply(clean_frag_id)
    comps = comps[comps['tmp_clean_id'].isin(list(comp_ds_list['comp_id']))]
    comps = comps.drop('tmp_clean_id', axis=1)

    # Build per-component conversion factor: Pelicun physical qty -> P-58 units
    comp_conversion = {}
    for _, _comp in comps.iterrows():
        _fid = clean_frag_id(_comp["ID"])
        _pelicun_unit = str(_comp["Units"]).strip()
        _attr_match = component_attributes[
            component_attributes['fragility_id'] == _fid
        ]
        if _attr_match.empty:
            comp_conversion[_fid] = 1.0
            continue
        _attr = _attr_match.iloc[0]
        comp_conversion[_fid] = _pelicun_to_p58_factor(
            _pelicun_unit, str(_attr['unit']).strip(), float(_attr['unit_qty'])
        )

    for _, comp in comps.iterrows():

        # clean periods from ID, then replace with underscore to match convention
        frag_id = clean_frag_id(comp['ID'])
        frag_id = frag_id.replace('.', '_')

        # initiate the frag_id column iff it doesn't exist
        if frag_id not in comp_population.columns:
            comp_population[frag_id] = 0.0

        story_sel = story_mask(comp["Location"], num_stories)

        dir_vec = np.array(
            str(comp["Direction"]).replace("0", "3").split(","),
            dtype=int
        )

        mask = (
            np.isin(comp_population.index.get_level_values("story"), stories[story_sel])
            & np.isin(comp_population.index.get_level_values("dir"), dir_vec)
        )

        _cfid = clean_frag_id(comp['ID'])
        comp_population.loc[mask, frag_id] += float(comp["Theta_0"]) * comp_conversion.get(_cfid, 1.0)

    comp_population.reset_index().to_csv(
        os.path.join(model_dir, "comp_population.csv"),
        index=False
    )


    #################### build simulated_damage.json
    # parse damage column metadata
    dmg_meta = []

    for col in damage.columns:
        parts = col.split("-")
        
    # find location of 'cmp-loc-dir-ds' and reassign
    # damage column convention: cmp-loc-dir-ds, B.10.44.101-1-2-1

        dmg_meta.append({
            "column": col,
            "frag_id": f"{parts[tag_name_list.index('cmp')]}",
            "story": int(parts[tag_name_list.index('loc')]),
            "dir": int(parts[tag_name_list.index('dir')]) or 3,
            "ds": int(parts[tag_name_list.index('ds')]),
        })

    dmg_meta = pd.DataFrame(dmg_meta)


    # Map (frag_id, ds_seq, ds_sub) -> column index in comp_ds_list
    comp_ds_list = comp_ds_list.reset_index(drop=True)
    comp_ds_list["lookup_key"] = (
        comp_ds_list["comp_id"]
        + "_"
        + comp_ds_list["ds_seq_id"].astype(str)
        + "_"
        + comp_ds_list["ds_sub_id"].astype(str)
    )

    lookup_index = {
        key: idx
        for idx, key in enumerate(comp_ds_list["lookup_key"])
    }

    num_reals = len(damage)
    num_ds = len(comp_ds_list)

    simulated_damage = {
        "story": {}
    }

    for s in range(1, num_stories + 1):
        simulated_damage["story"][s] = {
            "qnt_damaged": np.zeros((num_reals, num_ds)),
            "worker_days": np.zeros((num_reals, num_ds)),
            "repair_cost": np.zeros((num_reals, num_ds)),
            "qnt_damaged_dir_1": np.zeros((num_reals, num_ds)),
            "qnt_damaged_dir_2": np.zeros((num_reals, num_ds)),
            "qnt_damaged_dir_3": np.zeros((num_reals, num_ds)),
            "qnt_damaged_side_1": np.zeros((num_reals, num_ds)),
            "qnt_damaged_side_2": np.zeros((num_reals, num_ds)),
            "qnt_damaged_side_3": np.zeros((num_reals, num_ds)),
            "qnt_damaged_side_4": np.zeros((num_reals, num_ds)),
            "num_comps": np.zeros(num_ds),
        }

    
    # if no side-damage is specified, randomly distribute between 2 directions, then split between sides
    # two parallel sides will have the same damage
    if ratio_damage_per_side is None:
        ratio_damage_per_side = np.random.rand(num_reals,2) # assumes square footprint
        dmg_per_row = ratio_damage_per_side.sum(axis=1, keepdims=True)
        # normalize to 1, then split between two parallel sides
        ratio_damage_per_side = ratio_damage_per_side / dmg_per_row / 2 

    for _, meta in dmg_meta.iterrows():

        story = meta["story"]
        frag_id = meta["frag_id"]
        frag_id = clean_frag_id(frag_id)
        ds_seq = meta["ds"]
        dir_id = meta["dir"]
        col = meta["column"]

        if story not in simulated_damage["story"]:
            continue

        # Build lookup key (assume sub_id = 1 unless mapping requires otherwise)
        key = f"{frag_id}_{ds_seq}_1"

        if key not in lookup_index:
            continue

        # use lookup index to add damage sample 
        idx = lookup_index[key]

        dmg_data = np.array(damage[col].fillna(0), dtype=float)
        qnt_factor = comp_conversion.get(frag_id, 1.0)
        simulated_damage["story"][story]["qnt_damaged"][:, idx] += dmg_data * qnt_factor

        if col in DV_time.columns:
            repair_time_data = DV_time[col].fillna(0).astype(float)
            simulated_damage["story"][story]["worker_days"][:, idx] += repair_time_data

        if col in DV_cost.columns:
            repair_cost_data = DV_cost[col].fillna(0).astype(float)
            simulated_damage["story"][story]["repair_cost"][:, idx] += repair_cost_data
            
        
        simulated_damage["story"][story]["qnt_damaged_side_1"][:, idx] = ratio_damage_per_side[:,0]*simulated_damage["story"][story]["qnt_damaged"][:, idx]
        simulated_damage["story"][story]["qnt_damaged_side_2"][:, idx] = ratio_damage_per_side[:,1]*simulated_damage["story"][story]["qnt_damaged"][:, idx]
        simulated_damage["story"][story]["qnt_damaged_side_3"][:, idx] = ratio_damage_per_side[:,0]*simulated_damage["story"][story]["qnt_damaged"][:, idx]
        simulated_damage["story"][story]["qnt_damaged_side_4"][:, idx] = ratio_damage_per_side[:,1]*simulated_damage["story"][story]["qnt_damaged"][:, idx]

        # Direction-specific
        simulated_damage["story"][story][
            f"qnt_damaged_dir_{dir_id}"
        ][:, idx] += dmg_data * qnt_factor

        # add component quantity to simulated_damage
        for _, comp in comps.iterrows():
            frag_id = clean_frag_id(comp["ID"])
            theta = comp["Theta_0"]

            story_sel = story_mask(comp["Location"], num_stories)


            frag_matches = comp_ds_list["comp_id"] == frag_id

            for s_idx, is_story in enumerate(story_sel, start=1):
                if not is_story:
                    continue

            simulated_damage["story"][s_idx]["num_comps"][frag_matches] += theta * comp_conversion.get(frag_id, 1.0)

    ############# convert to json-serializable and save
    # Convert numpy arrays to lists 
    story_list = []
    tu_list = []

    # place damage breakdown into tu and story divisions
    # HP: if there is a category not covered below, it will be missed
    tenant_categories = ['repair_cost', 'num_comps', 'qnt_damaged',
                         'qnt_damaged_side_1', 'qnt_damaged_side_2', 
                         'qnt_damaged_side_3', 'qnt_damaged_side_4',
                         'worker_days']
    story_categories = ['qnt_damaged_dir_1', 'qnt_damaged_dir_2', 
                         'qnt_damaged_dir_3']

    for s in sorted(simulated_damage["story"].keys()):
        story_content = simulated_damage["story"][s]

        new_story = {
            k: (v.tolist() if hasattr(v, "tolist") else v)
            for k, v in story_content.items() if k in story_categories
        }
        story_list.append(new_story)

    for s in sorted(simulated_damage["story"].keys()):
        tu_content = simulated_damage["story"][s]

        new_tu = {
            k: (v.tolist() if hasattr(v, "tolist") else v)
            for k, v in tu_content.items() if k in tenant_categories
        }
        tu_list.append(new_tu)

    # Rebuild structure to match simulated_damage
    simulated_damage = {
        "tenant_units": tu_list,  
        "story": story_list
    }

    # # HP: some troubleshooting prints to verify rebuild 
    # print("QNT SUM:", np.sum(simulated_damage["tenant_units"][0]["qnt_damaged"]))
    # print("COST SUM:", np.sum(simulated_damage["tenant_units"][0]["repair_cost"]))
    # print("TIME SUM:", np.sum(simulated_damage["tenant_units"][0]["worker_days"]))

    output_path = os.path.join(model_dir, "simulated_damage.json")

    with open(output_path, "w") as f:
        json.dump(simulated_damage, f, indent=2)