from collections import OrderedDict
import numpy as np
import pandas as pd
from typing import Tuple
import xarray as xr

def extract_variables_from_dataset(ds: xr.Dataset, subset: OrderedDict):
    tensors = []
    for key, lev in subset.items():
        print(key, lev)
        values = None
        if isinstance(lev, bool):
            if lev:
                values = ds[key].values
        else:
            try:
                values = ds[key].sel(lev=list(lev)).values
            except Exception:
                print('Error',
                      # path, 
                      ds[key]['lev'])
                raise ValueError('error')

        if values is not None:
            if values.ndim == 2:
                values = values[None, ...]

            tensors.append(values)

    tensors = np.concatenate(tensors, axis=0)
    tensors = np.moveaxis(tensors, 0, -1)

    return tensors

    # Old version
    # data = []
    # for var in dataset.data_vars:
    #     var = var.lower()
    #     if subset is not None and var in subset:
    #         if subset[var] is not None:
    #             values = dataset[var].sel(lev=subset[var]).values
    #         else:
    #             continue
    #     else:
    #         values = dataset[var].values

    #     # For 2D dataarray, make it 3D.
    #     if len(np.shape(values)) != 3:
    #         values = np.expand_dims(values, 0)

    #     data.append(values)

    # # Reshape data so that it have channel_last format.
    # data = np.concatenate(data, axis=0)
    # data = np.moveaxis(data, 0, -1)

    # return data


def split_dataset_into_postive_negative_samples(dataset: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    positive_samples = dataset[dataset['TC']].reset_index()
    negative_samples = dataset[~dataset['TC']].reset_index()
    return positive_samples, negative_samples

def split_negative_samples_into_other_happening_tc_samples(negative_samples: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    assert 'Is Other TC Happening' in negative_samples.columns, 'Require labels .csv with v3+'
    other_tc_happening_samples = negative_samples[negative_samples['Is Other TC Happening']]
    negative_samples = negative_samples[~negative_samples['Is Other TC Happening']]
    return negative_samples.reset_index(), other_tc_happening_samples.reset_index()


def filter_negative_samples(dataset: pd.DataFrame, negative_samples_ratio=None, other_happening_tc_ratio=None):
    if negative_samples_ratio is None and other_happening_tc_ratio is None:
        return dataset

    print(dataset.head(5))
    positive_samples = dataset[dataset['TC']]
    samples = [positive_samples]
    has_is_other_tc_happening_column = 'Is Other TC Happening' in dataset.columns
    print(f'Positive samples: {len(positive_samples)}')

    # Make sure that we works seamlessly with labels v2 and v3+.
    negative_samples = (dataset[~dataset['TC'] & ~dataset['Is Other TC Happening']]
                        if has_is_other_tc_happening_column
                        else dataset[~dataset['TC']])
    if negative_samples_ratio is not None:
        nb_negative_samples_to_take = int(
            len(positive_samples) * negative_samples_ratio)
        negative_samples = negative_samples.sample(nb_negative_samples_to_take)
        samples.append(negative_samples)
    else:
        samples.append(negative_samples)

    print(f'Negative samples: {len(negative_samples)}')

    if other_happening_tc_ratio is not None:
        assert has_is_other_tc_happening_column, 'Require labels v3+ to filter out other happening tc ratio.'
        other_happening_tc_samples = dataset[~dataset['TC'] & dataset['Is Other TC Happening']]

        nb_other_happening_tc_to_take = int(len(positive_samples) * other_happening_tc_ratio)
        other_happening_tc_samples = other_happening_tc_samples.sample(nb_other_happening_tc_to_take)
        samples.append(other_happening_tc_samples)

        print(f'Other happening TC samples: {len(other_happening_tc_samples)}')
    else:
        # Make sure that we add all other TCs happening rows back to the original if possible!
        if has_is_other_tc_happening_column:
            samples.append(dataset[~dataset['TC'] & dataset['Is Other TC Happening']])

    result = pd.concat(samples)
    print(f'Total samples: {len(result)}')
    return result.sort_values(by='First Observed').reset_index()







