import numpy as np
import sys

def fn_inspection(is_essential_facility, is_borp_equivalent, surge_factor, 
                  sys_repair_trigger, inspection_trigger, trunc_pd, beta, 
                  impeding_factor_medians):
    '''Simulutes inspection time
   
    Parameters
    ----------
    is_essential_facility: logical
    is the building deemed essential by the local jurisdiction
      
    is_borp_equivalent: logical
    does the building have an inspector on retainer (BORP equivalent)
      
    surge_factor: number
    amplification factor for impedance time based on a post disaster surge
    in demand for skilled trades and construction supplies
      
    sys_repair_trigger: logical array [num_reals x num_systems]
      systems that require repair for each realization
      
    inpsection_trigger: logical array [num_reals x 1]
    defines which realizations require inspection
      
    trunc_pd: python (scipy) normal distribution object
    standard normal distrubtion, truncated at upper and lower bounds
      
    beta: number
    lognormal standard deviation (dispersion)
      
    impeding_factor_medians: DataFrame
    median delays for various impeding factors
   
    Returns
    -------
    inspection_imped: array [num_reals x num_sys]
    Simulated inspection time for each system '''
    
    ## Define inspection distribtuion parameters
    inspection_medians = impeding_factor_medians.loc[impeding_factor_medians['factor'] == 'inspection']
        
    if is_borp_equivalent == True:
        filt = np.array(inspection_medians['category']) =='borp'
        # BORP equivalent is not affected by surge
        median = np.array(inspection_medians['time_days'])[filt] 
    elif is_essential_facility == True:
        filt = np.array(inspection_medians['category']) =='essential'
        # BORP equivalent is not affected by surge
        median = np.array(inspection_medians['time_days'])[filt] * surge_factor
    else:
        filt = np.array(inspection_medians['category']) =='default'
        median = np.array(inspection_medians['time_days'])[filt] * surge_factor        
        
    ## Simulate 
    # Truncated lognormal distribution
    num_reals = len(inspection_trigger)
    prob_sim = np.random.rand(num_reals, 1)
    x_vals_std_n = trunc_pd.ppf(prob_sim)
    inspection_time = np.exp(x_vals_std_n * beta + np.log(median))
    
    # Only use realizations that require inpsection
    inspection_time[~inspection_trigger.astype(dtype=bool)] = 0
    
    # Affects all systems that need repair
    # Assume impedance always takes a full day
    inspection_imped = np.ceil(inspection_time * sys_repair_trigger) 
    
    return inspection_imped

def fn_financing(capital_available_ratio, funding_source, surge_factor, 
                 sys_repair_trigger, repair_cost_ratio, trunc_pd, beta, 
                 impeding_factor_medians):
    
    '''Simulutes financing time
     
    Parameters
    ----------
    capital_available_ratio: number
    liquidable funding on hand to make repairs immediately after the
    damaging event. Normalized by building replacment value.
    
    funding_source: string
    accepted values: {'sba', 'private', 'insurance'}
    type of funding source for required funds greater than the capital on
    hand
    
    surge_factor: number
    amplification factor for impedance time based on a post disaster surge
    sys_repair_trigger: logical array [num_reals x num_systems]
    systems that require repair for each realization
   
    repair_cost_ratio: array [num_reals x 1]
    simulated building repair cost; normalized by building replacemnt
    value.
    
    trunc_pd: python (scipy) normal distribution object
    standard normal distrubtion, truncated at upper and lower bounds
    
    beta: number
    lognormal standard deviation (dispersion)
    
    impeding_factor_medians: DataFrame
    median delays for various impeding factors
   
    Returns
    -------
    financing_imped: array [num_reals x num_sys]
    Simulated financing time for each system '''
    
    ## Define financing distribution parameters
    # Median financing times
    finance_medians = impeding_factor_medians.loc[impeding_factor_medians['factor'] == 'financing']
    
    # Required Financing
    financing_trigger = np.array(repair_cost_ratio) > capital_available_ratio
    
    if funding_source == 'sba': # SBA Backed Loans
        filt = np.array(finance_medians['category']) =='sba'
        # BORP equivalent is not affected by surge
        median = np.array(finance_medians['time_days'])[filt] * surge_factor # days
        
    elif funding_source == 'private': # SBA Backed Loans
        filt = np.array(finance_medians['category']) =='private'
        # BORP equivalent is not affected by surge
        median = np.array(finance_medians['time_days'])[filt] # days, not affected by surge

    elif funding_source == 'insurance': # SBA Backed Loans
        filt = np.array(finance_medians['category']) =='insurance'
        # BORP equivalent is not affected by surge
        median = np.array(finance_medians['time_days'])[filt] # days, not affected by surge        
        
    else: # Review this in relation to what is desired by MATLAB code
        print('Error! PBEE_Recovery:RepairSchedule - Invalid financing type for impedance factor simulation-funding_source')

    ## Simulate
    # Truncated lognormal distribution (via standard normal simulation)
    num_reals = len(repair_cost_ratio)
    prob_sim = np.random.rand(num_reals, 1)
    x_vals_std_n = trunc_pd.ppf(prob_sim)
    financing_time = np.exp(x_vals_std_n * beta + np.log(median))    

    
    # Only use realizations that require financing
    financing_time[~financing_trigger] = 0

    # Affects all systems that need repair
    # Assume impedance always takes a full day
    financing_imped = np.ceil(financing_time * sys_repair_trigger)
    
    return financing_imped 


def fn_permitting( num_reals, sys_repair_trigger, trunc_pd, 
                  beta, impeding_factor_medians):
    
    '''Simulutes permitting time
    
    Parameters
    ----------
    num_reals: int
    number of Monte Carlo simulations assessed
    
    surge_factor: number
    amplification factor for impedance time based on a post disaster surge
    in demand for skilled trades and construction supplies
    
    sys_repair_trigger: dictionary
    contains simulation data indicate if rapid permits or full permits are
    required for each system
    
    trunc_pd: python (scipy) normal distribution object
    standard normal distrubtion, truncated at upper and lower bounds
    
    beta: number
    lognormal standard deviation (dispersion)
    
    impeding_factor_medians: DataFrame
    median delays for various impeding factors
    
    Returns
    -------
    permitting_imped: array [num_reals x num_sys]
    Simulated permitting time for each system'''
    
    ## Define permitting distribution parameters
    # Find the median permit time for each system
    permit_medians = impeding_factor_medians.loc[impeding_factor_medians['factor'] == 'permitting']   
       
    # Rapid Permits
    filt = np.array(permit_medians['category']) =='rapid'
    rapid_permit_median = np.array(permit_medians['time_days'])[filt] # days
    
    # Full Permits
    filt = np.array(permit_medians['category']) =='full'
    full_permit_median = np.array(permit_medians['time_days'])[filt]  # days
    
    ## Simulate
    # Rapid Permits
    prob_sim = np.random.rand(num_reals, 1) # This assumes systems are correlated
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    rapid_permit_time = np.exp(x_vals_std_n * beta + np.log(rapid_permit_median))
    permitting_rapid = np.ceil(rapid_permit_time * sys_repair_trigger['rapid_permit']) # Assume impedance always takes a full day
    
    # Full Permits - simulated times are independent of rapid permit times
    prob_sim = np.random.rand(num_reals, 1); # This assumes systems are correlated
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    full_permit_time = np.exp(x_vals_std_n * beta + np.log(full_permit_median))
    permitting_full = np.ceil(full_permit_time * sys_repair_trigger['full_permit'])
       
    return permitting_rapid, permitting_full

def fn_contractor(num_reals, surge_factor, sys_repair_trigger, trunc_pd, contractor_options):

    '''Simulutes contractor mobilization time
    
    Parameters
    ----------
    num_sys: int
    number of building systems considered in the assessment
    
    num_reals: int
    number of Monte Carlo simulations assessed
    
    surge_factor: number
    amplification factor for impedance time based on a post disaster surge
    in demand for skilled trades and construction supplies
    sys_repair_trigger: logical array [num_reals x num_systems]
    systems that require repair for each realization
    
    systems: DataFrame
    data table containing information about each system's attributes
    
    contractor_options: 
    various options that controll the contracting impedance time
    
    Returns
    -------
    contractor_mob_imped: array [num_reals x num_sys]
    Simulated contractor mobilization time for each system'''
    
    ## Define contractor distribution parameters
    if contractor_options['contractor_relationship'] == 'retainer':
        med = surge_factor * contractor_options['contractor_retainer_time']
        beta = 0.4
    elif contractor_options['contractor_relationship'] == 'good':
        med = (1 + 0.5*(surge_factor-1)) * 3
        beta = 0.4
    elif contractor_options['contractor_relationship'] == 'none':
        med = surge_factor * 42
        beta = 0.8
    else:
        sys.exit('error! PBEE_Recovery:RepairSchedule. Invalid contractor relationship type for impedance factor simulation')

    ## Set median for each realization
    contr_med = med * np.ones([num_reals,1])
    
    ## Simulate Impedance Time
    prob_sim = np.random.rand(num_reals, 1) # This assumes systems are correlated
    x_vals_std_n = trunc_pd.ppf(prob_sim) # Truncated lognormal distribution (via standard normal simulation)
    contractor_mob_imped = np.exp(x_vals_std_n * beta + np.log(contr_med))
    
    # Only use the simulated values for the realzation and system that require permitting
    contractor_mob_imped = contractor_mob_imped * sys_repair_trigger

    # Amplify by the surge factor
    # Assume impedance always takes a full day
    contractor_mob_imped = np.ceil(contractor_mob_imped)
    
    return contractor_mob_imped


def fn_engineering(num_reals, repair_cost_ratio, building_value, surge_factor, 
                   redesign_trigger, is_engineer_on_retainer, user_options, 
                   design_min, design_max, trunc_pd, beta, 
                   impeding_factor_medians):
       
    '''Simulutes permitting time
      
    Parameters
    ----------
    num_reals: int
    number of Monte Carlo simulations assessed
    
    repair_cost_ratio: array [num_reals x 1]
    simulated building repair cost; normalized by building replacemnt
    value.
    
    building_value: number
    replacment value of building, in USD, non including land
    
    surge_factor: number
    amplification factor for impedance time based on a post disaster surge
    in demand for skilled trades and construction supplies
    
    redesign_trigger: logical array [num_reals x num_sys]
    is redesign required for the given system
    
    is_engineer_on_retainer: logical
    is there a pre-arranged agreement with an engineer for priorization of
    redesign
    
    user_options: dictionary
    contains paramters of system design time function, set by user
    design_min: row vector [1 x n_systems]
    lower bound on the median for each system
    
    design_max: row vector [1 x n_systems]
    upper bound on the median for each system
    
    trunc_pd: python (scipy) normal distribution object
    standard normal distrubtion, truncated at upper and lower bounds
    
    beta: number
    lognormal standard deviation (dispersion)
    
    impeding_factor_medians: DataFrame
    median delays for various impeding factors
   
    Returns
    -------
    eng_mob_imped: array [num_reals x num_sys]
    Simulated enginering mobilization time for each system
    
    eng_design_imped: array [num_reals x num_sys]
    Simulated enginering design time for each system
 
    Notes
    ------
    assumes engineering mobilization and re-design time are independant, but
    are correlated between each system. In other words, you will have the same 
    designers for the structural, stairs, exterior, and whatever other systems 
    need design time, but the time it takes to spin up an engineer is not
    related to the time it takes for them to complete the re-design.'''
    
    
    ## Engineering Mobilization Time
    # Mobilization medians
    eng_mob_medians = impeding_factor_medians.loc[impeding_factor_medians['factor'] == 'engineering mobilization']      
    
    if is_engineer_on_retainer == True:
        
        
        filt = np.array(eng_mob_medians['category']) =='retainer'
        
    else:
        filt = np.array(eng_mob_medians['category']) =='default'
        
    median_eng_mob = surge_factor * np.array(eng_mob_medians['time_days'])[filt] # days
    
    # Truncated lognormal distribution (via standard normal simulation)
    prob_sim = np.random.rand(num_reals, 1) # This assumes systems are correlated
    x_vals_std_n = trunc_pd.ppf(prob_sim)
    eng_mob_time = np.exp(x_vals_std_n * beta + np.log(median_eng_mob))

    # Assume impedance always takes a full day
    eng_mob_imped = np.ceil(eng_mob_time * redesign_trigger)
    
    ## Engineering Design Time
    ## Calculate System Design Time
    RC_total = np.array(repair_cost_ratio) * building_value;
    SDT = RC_total * user_options['f'] / (user_options['r'] * user_options['t'] * user_options['w'])     
    
    design_med=np.fmin(np.fmax(SDT, design_min), design_max).reshape(len(SDT),1)
     
    # Truncated lognormal distribution (via standard normal simulation)
    # Assumes engineering design time is independant of mobilization time
    prob_sim = np.random.rand(num_reals,1) # This assumes systems are correlated
    x_vals_std_n = trunc_pd.ppf(prob_sim)
    eng_design_time = np.exp(x_vals_std_n * beta + np.log(design_med))
    # Assume impedance always takes a full day
    eng_design_imped = np.ceil(eng_design_time * redesign_trigger)
    
    return eng_mob_imped, eng_design_imped  

def fn_default_surge_factor(is_dense_urban_area, pga, pga_de):
    '''This function determines the surge factor based on the intensity of shaking
      
       Parameters
       ----------
       is_dense_urban_area: bool
         if the building is in a dense urban area or not
       pga: number
         peak ground acceleration control point 1 (below which surge factor is 1)
       pga_de: number
         peak ground acceleration at the design intensity
      
      
       Returns
       -------
       surge_factor: number
         surge factor which amplified impedance factor times
      
       Notes
       -----
      
           |                                         _____________ 3.0
           |                                       /              
           |                                      /               
           |                                     /                
           |                                    /                 
           |                                   /                  
           |                                  /     ______________ 1.5
           |                                 /    / |             
           |                                /   /   |             
           |                               /  /     |             
           |                              / /       |             
           |                             //         |             
       1.0 |  __________________________/           |             
           |                            |           |             
           |                            |           |             
           -----------------------------+-----------+-------------
                                      pga_1       pga_2'''

    if is_dense_urban_area:
        max_surge = 3
    else:
        max_surge = 1.5
    
    pga_1 = max(0.2, pga_de);
    pga_2 = pga_1 * 1.5;
    surge_factor = np.interp(min(max(pga, pga_1), pga_2), [pga_1, pga_2], [1, max_surge])
    
    return surge_factor

    