def main_preprocessing(comp_ds_table, damage, repair_time_options, temp_repair_class, damage_consequences, num_stories):
    '''Parameterize variables and simplifying assumptions to expedite the ATC138
    recovery assessment

    Parameters
    ----------
    comp_ds_table: DataFrame
      various component attributes by damage state for each component 
      within the performance model. Can be populated from the 
      component_attribites.csv and damage_state_attribute_mapping.csv 
      databases in the static_tables directory.  Each row of the table 
      corresponds to each column of the simulated component damage arrays 
      within damage['tenant_units'].
    
    damage: dictionary
      contains simulated damage info and damage state attributes
    
    repair_time_options['allow_shoring']: logical
      flag indicating whether or not shoring should be considered as a
      temporary repair for local stability issues for structural components
    
    temp_repair_class: DataFrame
      attributes of each temporary repair class to consider
    
    damage_consequences: dictionary
      dictionary containing simulated building consequences, such as red
    
    num_stories: int
      Integer number of stories in the building being assessed

    Returns
    -------
    damage: dictionary
      contains simulated damage info and damage state attributes
    
    temp_repair_class: DataFrame
      attributes of each temporary repair class to consider
    
    damage_consequences: dictionary
      dictionary containing simulated building consequences, such as red'''
    
    import numpy as np
    from . import preprocessing_fns
    
    ## Define simulated damage in each tenant unit if not provided by the user
    damage = preprocessing_fns.fn_populate_damage_per_tu(damage)
    
    ##Simulate damage per side, if not provided by the user
    damage = preprocessing_fns.fn_simulate_damage_per_side(damage)
    
    ## Combine compoment attributes into recovery filters to expidite recovery assessment
    damage['fnc_filters'] = preprocessing_fns.fn_create_fnc_filters(comp_ds_table)
    
    ## Simulate Temporary Repair Times for each component
    damage, temp_repair_class = preprocessing_fns.fn_simulate_temp_worker_days(damage, temp_repair_class, repair_time_options)
    
    ## Set door racking damage if not provided by user
    damage_consequences = preprocessing_fns.fn_define_door_racking(damage_consequences, num_stories)
    
    return damage, temp_repair_class, damage_consequences

    
  
    