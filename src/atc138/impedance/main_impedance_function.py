def main_impeding_factors(damage, impedance_options, repair_cost_ratio_total, 
                          repair_cost_ratio_engineering, inspection_trigger, 
                          systems, tmp_repair_class, building_value, 
                          impeding_factor_medians, include_flooding_impact):

    '''Calculate ATC-138 impeding times for each system given simulation of damage
    
    Parameters (taken from Dustin's MATLAB file)
    ----------
    damage: dictionary
      contains per damage state damage and loss data for each component in the building
    
    impedance_options: dictionary
      general impedance assessment user inputs such as mitigation factors
    
    repair_cost_ratio: array [num_reals x 1]
      total repair cost per realization normalized by building replacement
      value
    
    inspection_trigger: logical array [num_reals x 1]
      defines which realizations require inspection
    
    num_stories: int
      Total number of building stories
    
    systems: DataFrame
      data table containing information about each system's attributes
    
    building_value: number
      The replacement value of the building, in USD
   
    impeding_factor_medians: table
      median delays for various impeding factors
   
    surge_factor: number
      amplification factor for imepding times due to materials and labor
      impacts due to regional damage
    
    Returns
    -------
    impedingFactors['time_sys']: array [num_reals x num_sys]
      Simulated total impeding time for each system
    
    impedingFactors['breakdown']: dictionary
      feilds: 'inspection', 'financing', 'eng_mob', 'design', 'permitting', 'contractor_mob'
      The simulated start day and complete day for each impeding factor,
      broken down per system where applicable
      
    
    Notes
    -----
    Correlation: Assuming factor-to-factor simulations are independent, but
    within a given factor, simulated system impedance time is fully
    correlated'''
    
    import numpy as np
    from scipy.stats import truncnorm
    
    from . import other_impedance_functions

    # Initialize parameters
    num_reals = len(inspection_trigger)
    num_sys = len(systems) # used height in MATLAB - Correlate with MATLAB at the time of running
    
    # Preallocate each impedance time
    duration={
    'inspection': np.zeros([num_reals, num_sys]),
    'financing': np.zeros([num_reals, num_sys]),
    'permit_rapid': np.zeros([num_reals, num_sys]),
    'permit_full': np.zeros([num_reals, num_sys]),
    'contractor_mob': np.zeros([num_reals, num_sys]),
    'eng_mob': np.zeros([num_reals, num_sys]),
    'design': np.zeros([num_reals, num_sys]),  
    'long_lead': np.zeros([num_reals, num_sys]), 
        }
    
    # System repair trigger
    # are there any repairs needed for this system
    # sys_repair_trigger = system_repair_time > 0
    
    # Create basic trucated standard normal distribution for later simulation
    th_low = -impedance_options['impedance_truncation']
    th_high = impedance_options['impedance_truncation']  
    mu = 0
    sigma = 1
    trunc_pd = truncnorm((th_low - mu)/sigma, (th_high - mu)/sigma, loc=mu, scale=sigma)
    beta = impedance_options['impedance_beta']

    ## Calculate Demand Surge (if applicble)
    if impedance_options['demand_surge']['include_surge'] ==1:
        surge_factor = other_impedance_functions.fn_default_surge_factor(impedance_options['demand_surge']['is_dense_urban_area'], 
                                               impedance_options['demand_surge']['site_pga'],
                                               impedance_options['demand_surge']['pga_de'])
    else:
        surge_factor = 1


    ## Parse through damage to determine which systems require repair
    
    sys_repair_trigger = {
        'any': np.zeros([num_reals, num_sys]),
        'rapid_permit' : np. zeros([num_reals, num_sys]),
        'full_permit' : np.zeros([num_reals, num_sys]),
        'redesign' : np. zeros([num_reals, num_sys]),
        'flooding' : np. zeros(num_reals)
        }
    for sys in range(num_sys):
        sys_filt = np.array(damage['comp_ds_table']['system']) == sys+1 #FZ +1 is done to coorrelate with python indexing starting from 0. 
        for tu in range(len(damage['tenant_units'])): 
            is_damaged = np.logical_and(np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0, np.array(damage['tenant_units'][tu]['worker_days']) > 0) # There is damage that needs to be fixed
            # Track if any damage exists that requires repair (assumes all
            # damage requires repair)
            sys_repair_trigger['any'][:,sys] = np.maximum(sys_repair_trigger['any'][:,sys] , np.amax((np.multiply( 1*(is_damaged) , 1*(sys_filt) )), axis=1))
            
            # Track if any damage exists that requires rapid permit per system
            sys_repair_trigger['rapid_permit'][:,sys] = np.maximum(sys_repair_trigger['rapid_permit'][:,sys] , np.amax((np.multiply( 1*(is_damaged) , ( 1*(sys_filt) & 1*(damage['fnc_filters']['permit_rapid'])))), axis=1))
            
            # Track if any damage exists that requires full permit per system
            sys_repair_trigger['full_permit'][:,sys] = np.maximum(sys_repair_trigger['full_permit'][:,sys] , np.amax((np.multiply( 1*(is_damaged) , ( 1*(sys_filt) & 1*(damage['fnc_filters']['permit_full'])))), axis=1))            
            
            # Track if any systems require redesign
            sys_repair_trigger['redesign'][:,sys] = np.maximum(sys_repair_trigger['redesign'][:,sys] , np.amax((np.multiply( 1*(is_damaged) , ( 1*(sys_filt) & 1*(damage['fnc_filters']['redesign'])))), axis=1))         

            # Track if any damage exists that triggers flooding
            sys_repair_trigger['flooding'] = np.maximum(sys_repair_trigger['flooding'], np.amax((np.multiply( 1*(is_damaged) , ( 1*(sys_filt) & 1*(damage['fnc_filters']['causes_flooding'])))), axis=1)) 
    
    # other_impedance_functions.
    # Simulate impedance time for each impedance factor 
        
    if impedance_options['include_impedance']['inspection'] == True:
       
        duration['inspection'] = other_impedance_functions.fn_inspection(impedance_options['mitigation']['is_essential_facility'],
            impedance_options['mitigation']['is_borp_equivalent'], 
            surge_factor, sys_repair_trigger['any'], inspection_trigger,
            trunc_pd, beta, impeding_factor_medians)
    
    if impedance_options['include_impedance']['financing'] == True:
       
        duration['financing'] = other_impedance_functions.fn_financing(impedance_options['mitigation']['capital_available_ratio'],
            impedance_options['mitigation']['funding_source'], 
            surge_factor, sys_repair_trigger['any'], repair_cost_ratio_total,
            trunc_pd, beta, impeding_factor_medians)
        
    if impedance_options['include_impedance']['permitting'] == True:
       
        duration['permit_rapid'], duration['permit_full'] = other_impedance_functions.fn_permitting(num_reals,
            sys_repair_trigger, trunc_pd,
            beta, impeding_factor_medians)
    
    
    if impedance_options['include_impedance']['contractor'] == True:    
        duration['contractor_mob'] = other_impedance_functions.fn_contractor(num_reals,
            surge_factor, sys_repair_trigger['any'], trunc_pd, impedance_options['mitigation'])
    
    if impedance_options['include_impedance']['engineering'] == True:     
        
        duration['eng_mob'], duration['design'] = other_impedance_functions.fn_engineering( num_reals,
            repair_cost_ratio_engineering, building_value, surge_factor,
            sys_repair_trigger['redesign'],
            impedance_options['mitigation']['is_engineer_on_retainer'],
            impedance_options['system_design_time'], impedance_options['eng_design_min_days'],
            impedance_options['eng_design_max_days'], trunc_pd, beta, impeding_factor_medians)

    if impedance_options['include_impedance']['long_lead'] == True:
        for sys in range(num_sys):
            sys_filt = damage['comp_ds_table']['system'] == sys+1   #FZ +1 is done to coorrelate with python indexing starting from 0.
            
            # Simulate long lead times. Assume long lead times are correlated among
            # all components within the system, but independant between systems
            prob_sim = np.random.rand(num_reals, 1) # Truncated lognormal distribution (via standard normal simulation)
            x_vals_std_n = trunc_pd.ppf(prob_sim) 
            sim_long_lead = np.exp(x_vals_std_n * beta + np.log(np.array(damage['comp_ds_table']['long_lead_time'])))
            
            for tu in range(len(damage['tenant_units'])):
                is_damaged = np.logical_and(np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0, np.array(damage['tenant_units'][tu]['worker_days']) > 0)
                
                #Track if any damage exists that requires repair (assumes all
                # damage requires repair). The long lead time for the system is
                # the max long lead time for any component within the system
                duration['long_lead'][:,sys] = np.maximum(duration['long_lead'][:,sys], 
                                                np.nanmax(is_damaged * sys_filt * sim_long_lead, axis=1))



    ## Aggregate experienced impedance time for each system/sequence and realization 
    # Figure out when each impeding factor finishes
    start_day = {'inspection' : np.zeros([num_reals,num_sys])}
    complete_day = {'inspection' : duration['inspection']}
    
    start_day['financing'] = complete_day['inspection']
    complete_day['financing'] = start_day['financing'] + duration['financing']
    
    start_day['eng_mob'] = np.maximum(complete_day['inspection'] ,start_day['financing'])
    complete_day['eng_mob'] = start_day['eng_mob'] + duration['eng_mob']
    
    start_day['design'] = complete_day['eng_mob']
    complete_day['design'] = start_day['design'] + duration['design']
    
    start_day['permit_rapid'] = complete_day['design']
    complete_day['permit_rapid'] = start_day['permit_rapid'] + duration['permit_rapid']
    
    start_day['permit_full'] = complete_day['design'];
    complete_day['permit_full'] = start_day['permit_full'] + duration['permit_full']
    
    start_day['contractor_mob'] = np.maximum(complete_day['inspection'], start_day['financing'])
    complete_day['contractor_mob'] = start_day['contractor_mob'] + duration['contractor_mob']
    
    # if impedance_options['include_impedance']['long_lead'] == True:
    start_day['long_lead'] = np.maximum(complete_day['inspection'] ,start_day['financing'])
    complete_day['long_lead'] = start_day['long_lead'] + duration['long_lead']
    
    # Combine all impedance factors by system
    impede_factors = np.array(list(complete_day.keys()));
    impeding_factors = {'time_sys' : 0}
    for i in range(len(impede_factors)):
        impeding_factors['time_sys'] = np.maximum(impeding_factors['time_sys'],
            complete_day[impede_factors[i]])
    
    ## Simulate Impeding Factors for Temporary Repairs
    # Determine median times for each system
    if impedance_options['mitigation']['contractor_relationship'] == 'retainer':
        temp_impede_med = surge_factor * np.array(tmp_repair_class['impeding_time']) # days
    elif impedance_options['mitigation']['contractor_relationship'] == 'good':
        temp_impede_med = surge_factor * np.array(tmp_repair_class['impeding_time']) # days
    elif impedance_options['mitigation']['contractor_relationship'] == 'none':
        temp_impede_med = surge_factor * np.array(tmp_repair_class['impeding_time_no_contractor']) # days        
    else:
        sys.exit('error! PBEE_Recovery:RepairSchedule. Invalid contractor relationship type for impedance factor simulation')

    # Find the which realization have damage that can be resolved by temp repairs
    tmp_repair_class_trigger = np.zeros([num_reals, len(tmp_repair_class)])
    for sys in range(len(tmp_repair_class)): 
        sys_filt = np.array(damage['comp_ds_table']['tmp_repair_class']) == sys+1
        for tu in range(len(damage['tenant_units'])):
            is_damaged = np.logical_and(np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0 , np.array( damage['tenant_units'][tu]['worker_days']) > 0)
            # Track if any damage exists that requires repair (assumes all damage requires repair)
            tmp_repair_class_trigger[:,sys] = np.maximum(tmp_repair_class_trigger[:,sys], np.nanmax(is_damaged * sys_filt, axis = 1))
   
    # Simulate Impedance Time
    prob_sim = np.random.rand(num_reals, 1) # This assumes systems are correlated
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    tmp_impede_sys = np.exp(x_vals_std_n * beta + np.log(temp_impede_med))
    
    # Only use the simulated values for the realzation and system that
    # trigger temporary repair damage
    tmp_impede_sys = tmp_impede_sys * tmp_repair_class_trigger
    
    # Assume impedance always takes a full day
    impeding_factors['temp_repair'] = {}
    impeding_factors['temp_repair']['time_sys'] = np.ceil(tmp_impede_sys)
    
    ## Simulate impeding factors and temp repair that occur in parallel with temp repair schedule
    # Temporary scaffolding for falling hazards
    prob_sim = np.random.rand(num_reals)
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    scaffold_impede_time = np.ceil(surge_factor * np.exp(x_vals_std_n * beta + np.log(impedance_options['scaffolding_lead_time']))) # always round up
    prob_sim = np.random.rand(num_reals) # repair time is not correlated to impedance time
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    scaffold_repair_time = np.exp(x_vals_std_n * beta + np.log(impedance_options['scaffolding_erect_time'])) 
    impeding_factors['temp_repair']['scaffold_day'] = np.ceil(scaffold_impede_time + scaffold_repair_time) # round up (dont resolve issue on the same day repairs are complete)   
    
    # Door Unjamming
    prob_sim = np.random.rand(num_reals)
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    impeding_factors['temp_repair']['door_racking_repair_day'] = np.ceil(surge_factor * np.exp(x_vals_std_n * beta + np.log(impedance_options['door_racking_repair_day']))) # always round up
    
    # Interior Flooding
    
    if include_flooding_impact == 1:
        # Flooding Cleanup
        prob_sim = np.random.rand(num_reals)
        x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
        impeding_factors['temp_repair']['flooding_cleanup_day'] = sys_repair_trigger['flooding'] * np.ceil(surge_factor * np.exp(x_vals_std_n * beta + np.log(impedance_options['flooding_cleanup_day']))) # always round up
    
        # Repair Flooding Damage
        prob_sim = np.random.rand(num_reals)
        x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
        impeding_factors['temp_repair']['flooding_repair_day'] = sys_repair_trigger['flooding'] * np.ceil(surge_factor * np.exp(x_vals_std_n * beta + np.log(impedance_options['flooding_repair_day']))) # always round up


    else: # zero out the flooding impedance (cleanup and repair)
        impeding_factors['temp_repair']['flooding_cleanup_day'] = np.zeros(num_reals)
        impeding_factors['temp_repair']['flooding_repair_day'] = np.zeros(num_reals)

    ## Format Impedance times for Gantt Charts                                                     
    # Full repair
    impeding_factors['breakdowns'] = {}
    
    impeding_factors['breakdowns']['full'] = {'inspection':{'start_day': np.nanmax(start_day['inspection'],1), 
                                                  'complete_day': np.nanmax(complete_day['inspection'],1)}} 
    impeding_factors['breakdowns']['full']['financing'] = {'start_day': np.nanmax(start_day['financing'],1), 
                                                  'complete_day': np.nanmax(complete_day['financing'],1)}                                    
    impeding_factors['breakdowns']['full']['contractor_mob'] = {'start_day': np.nanmax(start_day['contractor_mob'],1), 
                                                  'complete_day': np.nanmax(complete_day['contractor_mob'],1)}                                    
    impeding_factors['breakdowns']['full']['eng_mob'] = {'start_day': np.nanmax(start_day['eng_mob'],1), 
                                                  'complete_day': np.nanmax(complete_day['eng_mob'],1)}    
    impeding_factors['breakdowns']['full']['design'] = {'start_day': np.nanmax(start_day['design'],1), 
                                                  'complete_day': np.nanmax(complete_day['design'],1)}                                                        
    impeding_factors['breakdowns']['full']['permit_rapid'] = {'start_day': np.nanmax(start_day['permit_rapid'],1), 
                                                  'complete_day': np.nanmax(complete_day['permit_rapid'],1)}     
    impeding_factors['breakdowns']['full']['permit_full'] = {'start_day': np.nanmax(start_day['permit_full'],1), 
                                                  'complete_day': np.nanmax(complete_day['permit_full'],1)}    
    
    # Represent long lead times per system
    # if impedance_options['include_impedance']['long_lead'] == True:
    impeding_factors['breakdowns']['long_lead']= {}    
    for s in range(len(systems)):
        impeding_factors['breakdowns']['long_lead'][systems['name'][s]] = {'start_day' : start_day['long_lead'][:,s],
                                                                           'complete_day' : complete_day['long_lead'][:,s]}
    
    # Temporary Repairs
    impeding_factors['breakdowns']['temp'] = {}
    for tmp in range(len(tmp_repair_class)):
        impeding_factors['breakdowns']['temp'][tmp_repair_class['name_short'][tmp]] = {'start_day' : np.zeros(num_reals),
                                                                                       'complete_day' : impeding_factors['temp_repair']['time_sys'][:,0]}
        
    return impeding_factors