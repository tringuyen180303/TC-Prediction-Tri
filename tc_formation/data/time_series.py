import abc
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import partial
import tc_formation.data.label as label
import tc_formation.data.tfd_utils as tfd_utils
import tc_formation.data.utils as data_utils
import numpy as np
import os
import pandas as pd
import tensorflow as tf
from typing import List, Tuple
import xarray as xr


class TimeSeriesTropicalCycloneDataLoader:
    def __init__(self, data_shape, previous_hours:List[int] = [6, 12, 18], subset: OrderedDict = None):
        self._data_shape = data_shape
        self._previous_hours = previous_hours
        self._subset = subset

    def _load_tc_csv(self, data_path, leadtimes: List[int] = None) -> pd.DataFrame:
        return label.load_label(
                data_path,
                group_observation_by_date=True,
                leadtime=leadtimes)

    @classmethod
    def _add_previous_observation_data_paths(cls, path: str, previous_times: List[int]) -> List[str]:
        dirpath = os.path.dirname(path)
        name = os.path.basename(path)
        name, _ = os.path.splitext(name)
        # The date of the observation is embedded in the filename: `fnl_%Y%m%d_%H_%M.nc`
        name_parts = name.split('_')
        name_prefix = name_parts[0]
        date_part = ''.join('_'.join(name_parts[1:]))

        date = datetime.strptime(date_part, '%Y%m%d_%H_%M')

        previous_times = previous_times.copy()
        previous_times.sort()
        dates = [date - timedelta(hours=time) for time in previous_times]
        dates += [date]
        return [os.path.join(dirpath, f"{name_prefix}_{d.strftime('%Y%m%d_%H_%M')}.nc") for d in dates]

    @classmethod
    def _are_valid_paths(cls, paths: List[str]) -> bool:
        return all([os.path.isfile(p) for p in paths])

    @abc.abstractmethod
    def _process_to_dataset(self, tc_df: pd.DataFrame) -> tf.data.Dataset:
        pass

    def load_dataset_wip(
            self,
            data_path,
            shuffle=False,
            batch_size=64,
            caching=True,
            leadtimes: List[int]=None,
            nonTCRatio=None,
            other_happening_tc_ratio=None,
            **kwargs):
        cls = TimeSeriesTropicalCycloneDataLoader

        # Load TC dataframe.
        print('Dataframe loading.')
        tc_df = self._load_tc_csv(data_path, leadtimes)
        print('Dataframe in memory')
        tc_df['Path'] = tc_df['Path'].apply(
                partial(cls._add_previous_observation_data_paths, previous_times=self._previous_hours))
        print('Add previous hours')
        tc_df = tc_df[tc_df['Path'].apply(cls._are_valid_paths)]
        print('Check previous hours valid 2')

        # TODO:
        # can we move this into the dataset pipeline,
        # thus we can train the whole dataset without worrying about
        # unbalanced data.
        print('Dataframe loaded')
        if nonTCRatio is not None:
            datasets = []
            probs = []
            positive_samples, negative_samples = data_utils.split_dataset_into_postive_negative_samples(tc_df)

            # Process positive samples into dataset.
            positive_ds = self._process_to_dataset(positive_samples, **kwargs)
            datasets.append(positive_ds)
            probs.append(1.)

            if other_happening_tc_ratio is not None:
                negative_samples, other_tc_samples = data_utils.split_negative_samples_into_other_happening_tc_samples(negative_samples)

                negative_ds = self._process_to_dataset(negative_samples, **kwargs)
                datasets.append(negative_ds)
                probs.append(nonTCRatio)

                other_tc_ds = self._process_to_dataset(other_tc_samples, **kwargs)
                datasets.append(other_tc_ds)
                probs.append(other_happening_tc_ratio)
            else:
                negative_ds = self._process_to_dataset(negative_samples, **kwargs)
                datasets.append(negative_ds)
                probs.append(nonTCRatio)

            dataset = tf.data.Dataset.sample_from_datasets(datasets, weights=probs, stop_on_empty_dataset=True)
        else:
            dataset = self._process_to_dataset(tc_df, **kwargs)

        # if nonTCRatio is not None:
        #     nb_nonTC = int(round(len(tc_df[tc_df['TC']]) * nonTCRatio))
        #     with_tc_df = tc_df[tc_df['TC']]
        #     without_tc_df = tc_df[~tc_df['TC']].sample(nb_nonTC)
        #     tc_df = pd.concat([with_tc_df, without_tc_df], axis=0)
        #     tc_df.sort_values('Date', axis=0, inplace=True)


        # Convert to tf dataset.
        # dataset = self._process_to_dataset(tc_df, **kwargs)

        if caching:
            dataset = dataset.cache()

        if shuffle:
            dataset = dataset.shuffle(batch_size * 3)

        dataset = dataset.batch(batch_size)
        return dataset.prefetch(tf.data.AUTOTUNE)

    def load_dataset(
            self,
            data_path,
            shuffle=False,
            batch_size=64,
            caching=True,
            leadtimes: List[int]=None,
            nonTCRatio=None,
            other_happening_tc_ratio=None,
            **kwargs):
        cls = TimeSeriesTropicalCycloneDataLoader

        # Load TC dataframe.
        print('Dataframe loading.')
        tc_df = self._load_tc_csv(data_path, leadtimes)
        #print('before',  tc_df['Genesis'].sum())
        #print('Dataframe in memory')
        tc_df['Path'] = tc_df['Path'].apply(
                partial(cls._add_previous_observation_data_paths, previous_times=self._previous_hours))
        #print('before 1',  tc_df['Genesis'].sum())
        print('Add previous hours')
        tc_df = tc_df[tc_df['Path'].apply(cls._are_valid_paths)]
        print('Check previous hours valid')
        #print(f'Remaining rows: {len(tc_df)}')

        #print('total positives', tc_df['Genesis'].sum)
        # TODO:
        # can we move this into the dataset pipeline,
        # thus we can train the whole dataset without worrying about
        # unbalanced data.
        tc_df = data_utils.filter_negative_samples(
                tc_df,
                negative_samples_ratio=nonTCRatio,
                other_happening_tc_ratio=other_happening_tc_ratio)

        # if nonTCRatio is not None:
        #     nb_nonTC = int(round(len(tc_df[tc_df['TC']]) * nonTCRatio))
        #     with_tc_df = tc_df[tc_df['TC']]
        #     without_tc_df = tc_df[~tc_df['TC']].sample(nb_nonTC)
        #     tc_df = pd.concat([with_tc_df, without_tc_df], axis=0)
        #     tc_df.sort_values('Date', axis=0, inplace=True)

        print('Dataframe loaded')

        # Convert to tf dataset.
        dataset = self._process_to_dataset(tc_df, **kwargs)

        if shuffle:
            dataset = dataset.shuffle(batch_size * 3)

        if caching:
            dataset = dataset.cache()
        dataset = dataset.batch(batch_size)
        return dataset.prefetch(1)

    @abc.abstractmethod
    def load_single_data(self, data_path):
        ...

class TimeSeriesTropicalCycloneWithGridProbabilityDataLoader(TimeSeriesTropicalCycloneDataLoader):
    def __init__(self, tc_avg_radius_lat_deg=3, softmax_output=True, smooth_gt=False, clip_threshold=0.1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._softmax_output = softmax_output
        self._tc_avg_radius_lat_deg = tc_avg_radius_lat_deg
        self._clip_threshold = clip_threshold
        self._smooth_gt = smooth_gt

    def _process_to_dataset(self, tc_df: pd.DataFrame) -> tf.data.Dataset:
        cls = TimeSeriesTropicalCycloneWithGridProbabilityDataLoader
        #print(tc_df['Path'].sum())

        dataset = tf.data.Dataset.from_tensor_slices({
            'Path': np.asarray(tc_df['Path'].sum()).reshape((-1, len(self._previous_hours) + 1)),
            'TC': tc_df['TC'],
            'Latitude': tc_df['Latitude'],
            'Longitude': tc_df['Longitude'],
        })
        
        print('created dataset')
        
        dataset = dataset.map(
            lambda row: tfd_utils.new_py_function(
                    lambda row: cls._load_reanalysis_and_gt(
                            [path.decode('utf-8') for path in row['Path'].numpy()],
                            self._subset,
                            row['TC'].numpy(),
                            self._data_shape,
                            row['Latitude'].numpy(),
                            row['Longitude'].numpy(),
                            self._tc_avg_radius_lat_deg,
                            self._clip_threshold,
                            self._softmax_output,
                            self._smooth_gt,
                        ),
                    inp=[row],
                    Tout=[tf.float32, tf.float32],
                    name='load_observation_and_gt',
                ),
            #num_parallel_calls=tf.data.AUTOTUNE,
            num_parallel_calls = None,
            deterministic=False,
        )

        # Tensorflow should figure out the shape of the output of previous map,
        # but it doesn't, so we have to do it ourself.
        # https://github.com/tensorflow/tensorflow/issues/31373#issuecomment-524666365
        dataset = dataset.map(partial(
            cls._set_dataset_shape,
            shape=(len(self._previous_hours) + 1,) + self._data_shape,
            softmax_output=self._softmax_output))
        
        return dataset

    def load_single_data(self, data_row):
        cls = TimeSeriesTropicalCycloneWithGridProbabilityDataLoader

        paths = cls._add_previous_observation_data_paths(data_row['Path'], self._previous_hours)
        if not cls._are_valid_paths(paths):
            raise ValueError('Invalid data path: there are not enough observation paths.')

        data, gt = cls._load_reanalysis_and_gt(
            paths,
            self._subset,
            data_row['TC'],
            self._data_shape,
            data_row['Latitude'],
            data_row['Longitude'],
            self._tc_avg_radius_lat_deg,
            self._clip_threshold,
            self._softmax_output,
            self._smooth_gt,
        )
        return data, gt

    @classmethod
    def _set_dataset_shape(
            cls,
            data: tf.Tensor,
            gt: tf.Tensor,
            shape: tuple,
            softmax_output: bool):
        data.set_shape(shape)
        gt.set_shape(shape[1:3] + ((2,) if softmax_output else (1,)))
        return data, gt

    @classmethod
    def _load_reanalysis_and_gt(
            cls,
            paths: List[str],
            subset: OrderedDict,
            has_tc: bool,
            data_shape: tuple,
            tc_latitudes: float,
            tc_longitudes: float,
            tc_avg_radius_lat_deg: int,
            clip_threshold: float,
            softmax_output: bool,
            smooth_gt: bool,
        ) -> Tuple[np.ndarray, np.ndarray]:

        datasets = []
        for path in paths:
            dataset = xr.open_dataset(path, engine='netcdf4')
            latitudes = dataset['lat']
            longitudes = dataset['lon']
            dataset = data_utils.extract_variables_from_dataset(dataset, subset)
            datasets.append(np.expand_dims(dataset, axis=0))
        datasets = np.concatenate(datasets, axis=0)

        gt = cls._create_probability_grid_gt(
                has_tc,
                data_shape,
                latitudes,
                longitudes,
                tc_latitudes,
                tc_longitudes,
                softmax_output,
                smooth_gt,
                tc_avg_radius_lat_deg,
                clip_threshold,
            )

        return datasets, gt

    @classmethod
    def _create_probability_grid_gt(
            cls,
            has_tc: bool,
            data_shape: Tuple[int, int, int],
            latitudes: list,
            longitudes: list,
            tc_latitudes: float,
            tc_longitudes: float,
            softmax_output: bool,
            smooth_gt: bool,
            tc_avg_radius_lat_deg: int,
            clip_threshold: float,):
        groundtruth = np.zeros(data_shape[:-1])
        x, y = np.meshgrid(longitudes, latitudes)

        if has_tc:
            lats = tc_latitudes
            lons = tc_longitudes
            lats = lats if isinstance(lats, list) else [lats]
            lons = lons if isinstance(lons, list) else [lons]
            for lat, lon in zip(lats, lons):
                x_diff = x - lon
                y_diff = y - lat

                # RBF kernel.
                prob = np.exp(-(x_diff * x_diff + y_diff * y_diff)/(2 * tc_avg_radius_lat_deg ** 2))
                prob[prob < clip_threshold] = 0
                groundtruth += prob

        if not softmax_output:
            new_groundtruth = np.zeros(np.shape(groundtruth) + (1,))
            new_groundtruth[:, :, 0] = np.where(
                    groundtruth > 0,
                    1 if not smooth_gt else groundtruth,
                    0)
        else:
            new_groundtruth = np.zeros(np.shape(groundtruth) + (2,))
            new_groundtruth[:, :, 0] = np.where(groundtruth > 0, 0, 1)
            new_groundtruth[:, :, 1] = np.where(
                    groundtruth > 0,
                    1 if not smooth_gt else groundtruth,
                    0)

        return new_groundtruth

class TropicalCycloneWithGridProbabilityDataLoader(TimeSeriesTropicalCycloneWithGridProbabilityDataLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, previous_hours=[])

    def load_dataset(self, data_path, shuffle=False, batch_size=64, leadtimes: List[int]=None, nonTCRatio=None):
        def remove_time_dimension(X, y):
            return tf.squeeze(X, axis=1), y

        dataset = super().load_dataset(
                data_path=data_path,
                shuffle=shuffle,
                batch_size=batch_size,
                leadtimes=leadtimes,
                nonTCRatio=nonTCRatio)

        return dataset.map(remove_time_dimension)


class TimeSeriesTropicalCycloneWithLocationDataLoader(TimeSeriesTropicalCycloneDataLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _process_to_dataset(self, tc_df: pd.DataFrame) -> tf.data.Dataset:
        cls = TimeSeriesTropicalCycloneWithLocationDataLoader

        dataset = tf.data.Dataset.from_tensor_slices({
            'Path': np.asarray(tc_df['Path'].sum()).reshape((-1, len(self._previous_hours) + 1)),
            'TC': tc_df['TC'],
            'Latitude': tc_df['Latitude'],
            'Longitude': tc_df['Longitude'],
        })
        
        dataset = dataset.map(
            lambda row: tfd_utils.new_py_function(
                    lambda row: cls._load_reanalysis_and_loc(
                            [path.decode('utf-8') for path in row['Path'].numpy()],
                            self._subset,
                            row['TC'].numpy(),
                            row['Latitude'].numpy(),
                            row['Longitude'].numpy(),
                        ),
                    inp=[row],
                    Tout=[tf.float32, tf.float32],
                    name='load_observation_and_gt',
                ),
            num_parallel_calls= None,
            #num_parallel_calls=tf.data.AUTOTUNE,
            deterministic=False,
        )

        # Tensorflow should figure out the shape of the output of previous map,
        # but it doesn't, so we have to do it ourself.
        # https://github.com/tensorflow/tensorflow/issues/31373#issuecomment-524666365
        dataset = dataset.map(partial(
            cls._set_dataset_shape,
            shape=(len(self._previous_hours) + 1,) + self._data_shape,
        ))
        
        return dataset

    @classmethod
    def _load_reanalysis_and_loc(
            cls,
            paths: List[str],
            subset: OrderedDict,
            has_tc: bool,
            tc_latitudes: float,
            tc_longitudes: float,
        ) -> Tuple[np.ndarray, np.ndarray]:

        datasets = []
        for path in paths:
            dataset = xr.open_dataset(path, engine='netcdf4')
            dataset = data_utils.extract_variables_from_dataset(dataset, subset)
            datasets.append(np.expand_dims(dataset, axis=0))
        datasets = np.concatenate(datasets, axis=0)

        if has_tc:
            if isinstance(tc_latitudes, list):
                gt = np.asarray([1.0, tc_latitudes[0], tc_longitudes[0]])
            else:
                gt = np.asarray([1.0, tc_latitudes, tc_longitudes])
        else:
            gt = np.asarray([0, 0, 0])
            
        return datasets, gt

    @classmethod
    def _set_dataset_shape(
            cls,
            data: tf.Tensor,
            loc: tf.Tensor,
            shape: tuple):
        data.set_shape(shape)
        loc.set_shape((3,))
        return data, loc


class TropicalCycloneWithLocationDataLoader(TimeSeriesTropicalCycloneWithLocationDataLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, previous_hours=[])

    def load_dataset(self, data_path, shuffle=False, batch_size=64, leadtimes: List[int]=None, nonTCRatio=None):
        def remove_time_dimension(X, y):
            return tf.squeeze(X, axis=1), y

        dataset = super().load_dataset(
                data_path=data_path,
                shuffle=shuffle,
                batch_size=batch_size,
                leadtimes=leadtimes,
                nonTCRatio=nonTCRatio)

        return dataset.map(remove_time_dimension)
