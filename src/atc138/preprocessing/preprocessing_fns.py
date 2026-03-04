import numpy as np

def fn_populate_damage_per_tu(damage):
    
    '''Check to see if the damage.tenant_units variable has been defined. If
    not, assume its the same as damage.story. This assumption creates a 1:1
    coupling between stories and tenant_units (one tenant unit per story)
    
    Parameters
    ----------
    damage['story']: dictionary
    contains simulated per component and damage state damage info
    disagregated by story
    
    Returns
    -------
    contains simulated per component and damage state damage info
    disagregated by tenant unit'''

# If tenant unit damage is not provided by the user, assume its the same as per story damage

    if ('tenant_units' in damage.keys()) == False:
        damage['tenant_units'] = damage['story']
        
    return damage

def fn_simulate_damage_per_side(damage):
    '''Simulate damage per side for the exterior falling hazard check, if not 
    provided by the user. Component location within a story is typically not 
    Provided in most PBEE assessments. Therefore, this script make the rough 
    assumptions to distribute damage to 4 sides, randomly.
    
    Parameters
    ----------
    damage: dictionary
      contains simulated damage info and damage state attributes
    
    Returns
    -------
    damage: dictionary
      contains simulated damage info and damage state attributes'''
    
    
    # Simulate damage per side, if not provided by the user
    if ('qnt_damaged_side_1' in damage['tenant_units'][0].keys()) == False:
        num_reals = len(damage['tenant_units'][0]['qnt_damaged'])
        
        # Randomly split damage between 4 sides
        # (this will only matter for cladding components)
        ratio_damage_per_side = np.random.rand(num_reals,4) # assumes square footprint
        ratio_damage_per_side = ratio_damage_per_side / np.sum(ratio_damage_per_side, axis=1).reshape(num_reals,1) # force it to add to one
    
        # Assing damage
        for tu in range(len(damage['tenant_units'])):
            for s in range(4):
                damage['tenant_units'][tu]['qnt_damaged_side_' +str(s+1)] = ratio_damage_per_side[:,s].reshape(num_reals, 1) * np.array(damage['tenant_units'][tu]['qnt_damaged'])
                
    return damage

def fn_create_fnc_filters(comp_ds_table):
    '''Define function filter arrays that allow rapid sampling of simulated
    damage for use within the fault tree analysis

    Parameters
    ----------
    comp_ds_table: DataFrame
      various component attributes by damage state for each component 
      within the performance model. Can be populated from the 
      component_attribites.csv and damage_state_attribute_mapping.csv 
      databases in the static_tables directory.  Each row of the table 
      corresponds to each column of the simulated component damage arrays 
      within damage.tenant_units.

    Returns
    -------
    fnc_filters: dictionary
      each filter is a 1 x num_comp_ds array that can be used to sample
      select types of damage from the damage['tenant unit'] or damage['story']
      simulated damage arrays.'''


    # Convert damage['comp_ds_table'] lists to numpy arrays
    import numpy as np    
    
    comp_ds_table_keys = list(comp_ds_table.keys())
    
    for key in comp_ds_table_keys:
        comp_ds_table[key] = np.array(comp_ds_table[key])
        
    fnc_filters = {}  


    ## Impedance filters
    # fnc_filters['permit_rapid'] = strcmp(comp_ds_table.permit_type, 'rapid');
    # fnc_filters.permit_full = strcmp(comp_ds_table.permit_type, 'full');
    # fnc_filters.redesign = comp_ds_table.redesign == 1;
    fnc_filters['permit_rapid'] = comp_ds_table['permit_type'] == 'rapid'
    fnc_filters['permit_full'] = comp_ds_table['permit_type'] == 'full'
    fnc_filters['redesign'] = comp_ds_table['redesign'] == 1   
    
    # Building level filters
    '''combine all damage state filters that have the potential to affect
    function or reoccupancy, other than structural safety damage (for repair
    prioritization)'''
    
    fnc_filters['affects_reoccupancy'] = comp_ds_table['affects_envelope_safety'].astype('bool') | comp_ds_table['ext_falling_hazard'].astype('bool')  | comp_ds_table['int_falling_hazard'].astype('bool')  | comp_ds_table['global_hazardous_material'].astype('bool')  | comp_ds_table['local_hazardous_material'].astype('bool') | comp_ds_table['affects_access'].astype('bool')
    fnc_filters['affects_function'] = fnc_filters['affects_reoccupancy'] | comp_ds_table['damages_envelope_seal'].astype('bool') | comp_ds_table['obstructs_interior_space'].astype('bool') | comp_ds_table['impairs_system_operation'].astype('bool') 
    
    # Define when building has resolved its red tag (when all repairs are complete that may affect red tags)
    # get any components that have the potential to cause red tag
    fnc_filters['red_tag'] = comp_ds_table['safety_class'] > 0
    
    # Define when the building requires shoring from external falling hazards
    fnc_filters['requires_shoring'] = comp_ds_table['requires_shoring'].astype('bool')
    
    # Define when the building has issues with internal flooding
    fnc_filters['causes_flooding'] = comp_ds_table['causes_flooding'].astype('bool')
    
    ## System dependent filters
    # fire suppresion system damage that affects entire building
    fnc_filters['fire_building'] = np.logical_and(comp_ds_table['system'] == 9, np.logical_and(comp_ds_table['service_location'] == 'building' , comp_ds_table['impairs_system_operation'] == 1))
    
    # fire suppresion damage that affects each tenant unit
    fnc_filters['fire_unit'] = np.logical_and(comp_ds_table['system'] == 9, np.logical_and(comp_ds_table['subsystem_id'] == 23, np.logical_and(comp_ds_table['service_location'] == 'unit' , comp_ds_table['impairs_system_operation'] == 1))) # pipe and brace branches (not spinkler heads)
    fnc_filters['fire_drops'] = np.logical_and(comp_ds_table['subsystem_id'] == 23, comp_ds_table['impairs_system_operation'] == 1)
    
    # Hazardous materials
    fnc_filters['global_hazardous_material'] = comp_ds_table['global_hazardous_material'].astype('bool')
    fnc_filters['local_hazardous_material'] = comp_ds_table['local_hazardous_material'].astype('bool')
    
    # Stairs
    fnc_filters['stairs'] = np.logical_and(comp_ds_table['affects_access'] == 1, comp_ds_table['system'] == 4)
    
    # Exterior enclosure damage
    fnc_filters['exterior_safety_lf'] = np.logical_and(comp_ds_table['unit'] == 'lf', comp_ds_table['affects_envelope_safety'] == 1) # Components with perimeter linear feet units
    fnc_filters['exterior_safety_sf'] = np.logical_and(comp_ds_table['unit'] == 'sf' , comp_ds_table['affects_envelope_safety'] == 1) # Components with perimeter square feet units
    fnc_filters['exterior_safety_all'] = fnc_filters['exterior_safety_lf'] | fnc_filters['exterior_safety_sf']
    
    # Exterior Falling hazards
    fnc_filters['ext_fall_haz_lf'] = np.logical_and(comp_ds_table['unit'] =='lf', comp_ds_table['ext_falling_hazard'] == 1) # Components with perimeter linear feet units
    fnc_filters['ext_fall_haz_sf'] = np.logical_and(comp_ds_table['unit'] == 'sf', comp_ds_table['ext_falling_hazard'] == 1) # Components with square feet units
    fnc_filters['ext_fall_haz_ea'] = np.logical_and(comp_ds_table['unit'] == 'each', comp_ds_table['ext_falling_hazard'] == 1) # Components with "each" units
    fnc_filters['ext_fall_haz_all'] = fnc_filters['ext_fall_haz_lf'] | fnc_filters['ext_fall_haz_sf'] | fnc_filters['ext_fall_haz_ea']
    
    # Exterior enclosure envelope seal damage
    fnc_filters['exterior_seal_lf'] = np.logical_and(comp_ds_table['unit'] == 'lf', comp_ds_table['damages_envelope_seal'] == 1) # Components with perimeter linear feet units
    fnc_filters['exterior_seal_sf'] = np.logical_and(comp_ds_table['unit'] == 'sf', comp_ds_table['damages_envelope_seal'] == 1) # Components with perimeter square feet units
    fnc_filters['exterior_seal_ea'] = np.logical_and(comp_ds_table['unit'] == 'each', comp_ds_table['damages_envelope_seal'] == 1) # Components with perimeter each units    
    fnc_filters['exterior_seal_all'] = fnc_filters['exterior_seal_lf'] | fnc_filters['exterior_seal_sf'] | fnc_filters['exterior_seal_ea']
    
    # Roofing components
    fnc_filters['roof_structure'] = np.logical_and(comp_ds_table['subsystem_id'] == 21, comp_ds_table['affects_roof_function'] == 1)
    fnc_filters['roof_weatherproofing'] = np.logical_and(comp_ds_table['subsystem_id'] == 22, comp_ds_table['affects_roof_function'] == 1)
    
    # Interior falling hazards
    fnc_filters['int_fall_haz_lf'] = np.logical_and(comp_ds_table['int_falling_hazard'] == 1, np.logical_and(comp_ds_table['unit'] == 'lf', comp_ds_table['interior_area_conversion_type'] == 'component')) # Interior components with perimeter feet units
    fnc_filters['int_fall_haz_sf'] = np.logical_and(comp_ds_table['int_falling_hazard'] == 1, np.logical_and(comp_ds_table['unit'] == 'sf', comp_ds_table['interior_area_conversion_type'] == 'component')) # Interior components with area feet units
    fnc_filters['int_fall_haz_ea'] = np.logical_and(comp_ds_table['int_falling_hazard'] == 1, np.logical_and(comp_ds_table['unit'] == 'each', comp_ds_table['interior_area_conversion_type'] == 'component')) # Interior components with "each" for units (just scale directly)    
    fnc_filters['int_fall_haz_bay'] = np.logical_and(comp_ds_table['int_falling_hazard'] == 1, comp_ds_table['interior_area_conversion_type'] == 'bay') # structural damage that does not cause red tags but affects function
    fnc_filters['int_fall_haz_build'] = np.logical_and(comp_ds_table['int_falling_hazard'] == 1, comp_ds_table['interior_area_conversion_type'] == 'building') # structural damage that does not cause red tags but affects funciton (this one should only be tilt-ups)
    fnc_filters['int_fall_haz_all'] = fnc_filters['int_fall_haz_lf'] | fnc_filters['int_fall_haz_sf'] | fnc_filters['int_fall_haz_ea'] | fnc_filters['int_fall_haz_bay'] | fnc_filters['int_fall_haz_build'] 
    fnc_filters['vert_instabilities'] = np.logical_and(comp_ds_table['system'] == 1, comp_ds_table['int_falling_hazard'] == 1)
    
    # Interior function damage 
    fnc_filters['interior_function_lf'] = np.logical_and(comp_ds_table['obstructs_interior_space'] == 1, np.logical_and(comp_ds_table['unit'] == 'lf', comp_ds_table['interior_area_conversion_type'] == 'component')) 
    fnc_filters['interior_function_sf'] = np.logical_and(comp_ds_table['obstructs_interior_space'] == 1, np.logical_and(comp_ds_table['unit'] == 'sf', comp_ds_table['interior_area_conversion_type'] == 'component')) 
    fnc_filters['interior_function_ea'] = np.logical_and(comp_ds_table['obstructs_interior_space'] == 1, np.logical_and(comp_ds_table['unit'] == 'each', comp_ds_table['interior_area_conversion_type'] == 'component'))     
    fnc_filters['interior_function_bay'] = np.logical_and(comp_ds_table['obstructs_interior_space'] == 1, comp_ds_table['interior_area_conversion_type'] == 'bay')
    fnc_filters['interior_function_build'] = np.logical_and(comp_ds_table['obstructs_interior_space'] == 1, comp_ds_table['interior_area_conversion_type'] == 'building')  
    fnc_filters['interior_function_all'] = fnc_filters['interior_function_lf'] | fnc_filters['interior_function_sf'] | fnc_filters['interior_function_ea'] | fnc_filters['interior_function_bay'] | fnc_filters['interior_function_build'] 
    
    # Elevators
    fnc_filters['elevators'] = np.logical_and(comp_ds_table['system'] == 5, np.logical_and(comp_ds_table['impairs_system_operation'], comp_ds_table['subsystem_id'] != 2))
    fnc_filters['elevator_mcs'] = np.logical_and(comp_ds_table['system'] == 5, np.logical_and(comp_ds_table['impairs_system_operation'], comp_ds_table['subsystem_id'] == 2))
    
    # Electrical system
    fnc_filters['electrical_main'] = np.logical_and(comp_ds_table['system'] == 7, np.logical_and(comp_ds_table['subsystem_id'] == 1, np.logical_and(comp_ds_table['service_location'] == 'building', comp_ds_table['impairs_system_operation'] == 1)))
    fnc_filters['electrical_unit'] = np.logical_and(comp_ds_table['system'] == 7, np.logical_and(comp_ds_table['subsystem_id'] == 1, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] == 1)))
    
    # Water and Plumbing
    # Potable Water Plumping
    fnc_filters['water_main'] = np.logical_and(comp_ds_table['system'] == 6, np.logical_and(comp_ds_table['subsystem_id'] == 8, np.logical_and(comp_ds_table['service_location'] == 'building', comp_ds_table['impairs_system_operation'] == 1)))
    fnc_filters['water_unit'] = np.logical_and(comp_ds_table['system'] == 6, np.logical_and(comp_ds_table['subsystem_id'] == 8, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] == 1)))
    
    # Sanitary Plumbing
    fnc_filters['sewer_main'] = np.logical_and(comp_ds_table['system'] == 6 , np.logical_and(comp_ds_table['subsystem_id'] == 9, np.logical_and(comp_ds_table['service_location'] == 'building', comp_ds_table['impairs_system_operation'] ==1)))
    fnc_filters['sewer_unit'] = np.logical_and(comp_ds_table['system'] == 6 , np.logical_and(comp_ds_table['subsystem_id'] == 9, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] ==1)))

  
    # HVAC
    fnc_filters['hvac'] = {}
    
    fnc_filters['hvac'] = {'building': 
                        {'hvac_control': {},
                         'hvac_heating': {},
                         'hvac_cooling': {}
                         },
                       'tenant':
                        {'hvac_ventilation': {},
                         'hvac_heating': {},
                         'hvac_cooling': {},
                         'hvac_exhaust': {}
                         }
                        }
                                                
    
    # HVAC: Control System
    
    fnc_filters['hvac']['building']['hvac_control']['mcs'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 2, comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['hvac']['building']['hvac_control']['control_panel'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 20, comp_ds_table['impairs_system_operation'] == 1))

    # HVAC: Ventilation
    fnc_filters['hvac']['tenant']['hvac_ventilation']['duct_mains'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 24, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] == 1)))
    fnc_filters['hvac']['tenant']['hvac_ventilation']['duct_braches'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 4, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] == 1)))
    fnc_filters['hvac']['tenant']['hvac_ventilation']['in_line_fan'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 5, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] == 1))) 
    fnc_filters['hvac']['tenant']['hvac_ventilation']['duct_drops'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 6, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] == 1)))
    fnc_filters['hvac']['tenant']['hvac_ventilation']['ahu'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 19, comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['hvac']['tenant']['hvac_ventilation']['rtu'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 17, comp_ds_table['impairs_system_operation'] == 1))

    # HVAC: Heating
    fnc_filters['hvac']['building']['hvac_heating']['piping'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 10, comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['hvac']['tenant']['hvac_heating']['vav'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 7, comp_ds_table['impairs_system_operation'] == 1))

    # HVAC: Cooling
    fnc_filters['hvac']['building']['hvac_cooling']['piping'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 11, comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['hvac']['building']['hvac_cooling']['chiller'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 15, comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['hvac']['building']['hvac_cooling']['cooling_tower'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 16, comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['hvac']['tenant']['hvac_cooling']['vav'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 7, comp_ds_table['impairs_system_operation'] == 1))

    # HVAC: Exhaust
    fnc_filters['hvac']['tenant']['hvac_exhaust']['exhaust_fan'] = np.logical_and(comp_ds_table['system'] == 8, np.logical_and(comp_ds_table['subsystem_id'] == 18, comp_ds_table['impairs_system_operation'] == 1))
    
    # Data system
    fnc_filters['data_main'] = np.logical_and(comp_ds_table['system'] == 11, np.logical_and(comp_ds_table['service_location'] == 'building', comp_ds_table['impairs_system_operation'] == 1))
    fnc_filters['data_unit'] = np.logical_and(comp_ds_table['system'] == 11, np.logical_and(comp_ds_table['service_location'] == 'unit', comp_ds_table['impairs_system_operation'] ==1))
    
    # Horizontal Egress: Fire break partitions
    fnc_filters['fire_break'] = np.logical_and(comp_ds_table['system'] == 3, comp_ds_table['weakens_fire_break'] == 1) # only collect interior fire break partitions
    
    return fnc_filters

    
def fn_simulate_temp_worker_days(damage, temp_repair_class, repair_time_options):
    '''Simulate Temporary Repair Times for each component, if not already
        defined by the user. In a perfect system this should be done alongside 
        the other full repair time simulation. However, most PBEE assessments do
        not contain information on temp repair times per component when they are
        simulating damage and consequences. Therefore, this is decoupled from the
        rest of the assessment and simulated here (if not already provided by the
        user)
        
        Parameters
        ----------
        damage: dictionary
          contains simulated damage info and damage state attributes
        repair_time_options['allow_shoring']: logical
          flag indicating whether or not shoring should be considered as a
          temporary repair for local stability issues for structural components
        temp_repair_class: DataFrame
          attributes of each temporary repair class to consider
        
        Returns
        -------
        damage: dictionary
          contains simulated damage info and damage state attributes
        temp_repair_class: DataFrame
          attributes of each temporary repair class to consider'''
        
        
    ## Define Temporary Repair Times Options
    # Turn of temp repairs if specificied by the user
    if ('allow_tmp_repairs' in repair_time_options.keys()) == False:
        damage['comp_ds_table']['tmp_repair_class'] = np.zeros(np.shape(damage['comp_ds_table']['tmp_repair_class']))
 
    # Set up temp_repair_class based on user inputs
    if ('allow_shoring' in repair_time_options.keys()) == False:
        temp_repair_class.drop(temp_repair_class.index[temp_repair_class['id'] == 5], inplace=True)

    ## Simulate temp repair worker days per component
    # if not already specified by the user
    if ('tmp_worker_day' in damage['tenant_units'][0].keys()) == False:
        # Find total number of damamged components
        total_damaged = np.array(damage['tenant_units'][0]['qnt_damaged']).copy()
        for tu in range(len(damage['tenant_units'])-1):
            total_damaged = total_damaged + np.array(damage['tenant_units'][tu+1]['qnt_damaged'])
    
        # Aggregate the total number of damaged components accross each damage
        # state in a component
        num_reals = len(damage['tenant_units'][0]['qnt_damaged']) 
        tmp_worker_days_per_unit = np.zeros([num_reals, len(damage['comp_ds_table']['comp_id'])])
        for c in range(len(damage['comp_ds_table']['comp_id'])): # for each comp ds
            # comp = comp_ds_table(c,:);
            if damage['comp_ds_table']['tmp_repair_class'][c] > 0: # For damage that has temporary repair
                filt = np.array(damage['comp_ds_table']['comp_id']) == damage['comp_ds_table']['comp_id'][c]
                total_damaged_all_ds = np.sum(total_damaged[:,filt], axis=1)
            
                if float(damage['comp_ds_table']['tmp_repair_time_lower_qnty'][c]) == float(damage['comp_ds_table']['tmp_repair_time_upper_qnty'][c]):
                    tmp_worker_days_per_unit[:,c] = damage['comp_ds_table']['tmp_repair_time_lower'][c]
                else:
                # Interpolate to get per unit temp repair times
                    tmp_worker_days_per_unit[:,c] = np.interp(np.minimum(np.maximum(total_damaged_all_ds, float(damage['comp_ds_table']['tmp_repair_time_lower_qnty'][c])), float(damage['comp_ds_table']['tmp_repair_time_upper_qnty'][c])),
                                np.array([float(damage['comp_ds_table']['tmp_repair_time_lower_qnty'][c]), float(damage['comp_ds_table']['tmp_repair_time_upper_qnty'][c])]),
                                np.array([damage['comp_ds_table']['tmp_repair_time_lower'][c], damage['comp_ds_table']['tmp_repair_time_upper'][c]]),
                                )
            else:
                tmp_worker_days_per_unit[:,c] = np.nan

        '''Simulate uncertainty in per unit temp repair times
        Assumes distribution is lognormal with beta = 0.4
        Assumes time to repair all of a given component group is fully correlated, 
        but independant between component groups''' 
        
        sim_tmp_worker_days_per_unit = np.random.lognormal(np.log(tmp_worker_days_per_unit), 0.4, np.shape(tmp_worker_days_per_unit))
        
        # Allocate per unit temp repair time among tenant units to calc worker days
        # for each component
        for tu in range(len(damage['tenant_units'])):
            damage['tenant_units'][tu]['tmp_worker_day'] = np.array(damage['tenant_units'][tu]['qnt_damaged']) * sim_tmp_worker_days_per_unit

    return damage, temp_repair_class

def fn_define_door_racking(damage_consequences, num_stories):
    '''Define building level damage consquences when not specificed by the user.
    
    Parameters
    ----------
    damage_consequences: dictionary
      dictionary containing simulated building consequences, such as red
      tags
    num_stories: int
      Integer number of stories in the building being assessed
    
    Returns
    -------
    damage_consequences['racked_stair_doors_per_story']: array, num real x num stories
      simulated number of racked stairwell doors at each story
    damage_consequences['racked_entry_doors_side_1']: array, num real x 1
      simulated number of racked entry doors on one side of the building
    damage_consequences['racked_entry_doors_side_2']: array, num real x 1
      simulated number of racked entry doors on the other side of the building'''
    
    ## Set door racking damage if not provided by user
    num_reals = len(damage_consequences['simulated_replacement_time'])
    
    # Assume there are no racked doors if not specified by the user
    if ('racked_stair_doors_per_story' in damage_consequences.keys()) == False:
        damage_consequences['racked_stair_doors_per_story'] = (np.zeros([num_reals,num_stories])).tolist() #num real x num stories

    if ('racked_entry_doors_side_1' in damage_consequences.keys()) == False:
        damage_consequences['racked_entry_doors_side_1'] = list(np.zeros(num_reals)) 

    if ('racked_entry_doors_side_2' in damage_consequences.keys()) == False:
        damage_consequences['racked_entry_doors_side_2'] = list(np.zeros(num_reals))
    
    return damage_consequences



