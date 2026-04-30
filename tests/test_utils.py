import atc138.driver
from pathlib import Path
import shutil
import pandas as pd

def copy_defaults(case_dir: Path, default_path: Path):
    case_dir.mkdir(parents=True, exist_ok=True)

    for f in ['optional_inputs.json',
              'tenant_function_requirements.csv',
              'tenant_unit_list.csv']:
        
        shutil.copy(default_path / f, case_dir / f)

def cleanup(case_dir: Path):
    # remove intermediate files only
    for f in case_dir.glob("simulated_inputs.json"):
        f.unlink()

def run_atc138(case_dir: Path, num_iter=1):
    '''
    Functionality to run the extended/canonical test suites. On the first run, rebuild the input file. On the last run,
    cleanup the large input file.

    case_dir: directory of folder containing the input files
    num_iter: Number of iterations to be ran. Seeds will be created from 1-num_iter

    '''
    print(f"Running {case_dir}")

    # path_to_defaults = case_dir.parent.parent / 'atcpy_input'
    # copy_defaults(case_dir, default_path=path_to_defaults)

    # define outputs explicitly
    output_dir = case_dir / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    comp_population_csv = case_dir / 'comp_population.csv'

    if not comp_population_csv.is_file():
        cmp_pop = pd.read_excel(case_dir / 'comp_population.xlsx')

        # handle duplicate components in xlsx by summing
        # strip all trailing duplicate naming convention of ".1" ".2"
        # IMPORTANT: this can handle only up to 10 duplicates
        cmp_pop.columns = cmp_pop.columns.str.replace(r'\.\d$', '', regex=True)

        # group & sum
        cmp_pop_sum = cmp_pop.T.groupby(level=0).sum().T
        meta_cols = ['story', 'dir']
        cmp_pop_sum = cmp_pop_sum.astype({'story': int, 'dir': int})
        cmp_pop_sum = cmp_pop_sum[meta_cols + [col for col in cmp_pop_sum.columns if col not in meta_cols]]

        cmp_pop_sum.to_csv(comp_population_csv, index=False)

    # run analysis
    if num_iter > 1:
        for run_no in range(1, num_iter+1):
            output_file = f'recovery_outputs_run{run_no}.json'
            if run_no == 1:
                atc138.driver.run_analysis(
                    case_dir, output_dir, seed=run_no, output_file=output_file, force_rebuild=True)
            else:
                atc138.driver.run_analysis(
                    case_dir, output_dir, seed=run_no, output_file=output_file, force_rebuild=False)

    else:
        atc138.driver.run_analysis(case_dir, output_dir, seed=985, force_rebuild=True)

    # cleanup
    cleanup(case_dir)

def batch_run_folder(root_dir: Path, n_iter=1):
    '''
    go through each folder and run atc138

    supports either a flat directory or a nested directory (i.e. of IM folders)
    '''
    
    # case 1: no IMs and building_model.json is directly in dir
    building_model_file = root_dir / 'building_model.json'
    if building_model_file.is_file():
        run_atc138(root_dir, n_iter)
    # case 2: models are nested within experiment directories
    else:
        for im_dir in root_dir.iterdir():
            if not im_dir.is_dir():
                continue
            run_atc138(im_dir, n_iter)