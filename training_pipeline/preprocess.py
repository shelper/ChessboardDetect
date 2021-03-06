# Methods to load datasets from folders, preprocess them,
# and build input functions for the estimators.
import tensorflow as tf
import glob
import numpy as np
from tensorflow.contrib.data import Dataset
import random

def loadMultipleDatapaths(parent_folder_list, max_count_each_entries=None, pre_shuffle=False, do_shuffle=True, make_equal=False):
  # Pass list of folder paths
  filepaths_good = []
  filepaths_bad = []
  for parent_folder in parent_folder_list:
    folder_filepaths_good = glob.glob("%s/good/*.png" % parent_folder)
    folder_filepaths_bad = glob.glob("%s/bad/*.png" % parent_folder)

    if pre_shuffle:
      # Shuffle individual folder paths
      random.shuffle(folder_filepaths_good)
      random.shuffle(folder_filepaths_bad)

    if max_count_each_entries:
      folder_filepaths_good = folder_filepaths_good[:max_count_each_entries]
      folder_filepaths_bad = folder_filepaths_bad[:max_count_each_entries]

    filepaths_good.extend(folder_filepaths_good)
    filepaths_bad.extend(folder_filepaths_bad)

  # Make count of good and bad equal
  if make_equal:
    n_each = min(len(filepaths_good), len(filepaths_bad))
    filepaths_good = filepaths_good[:n_each]
    filepaths_bad = filepaths_bad[:n_each]

  N_good, N_bad = len(filepaths_good), len(filepaths_bad)

  # Set up labels
  labels = np.array([1]*N_good + [0]*N_bad, dtype=np.float64)

  # Shuffle all entries keeping labels and paths together.
  entries = zip(filepaths_good + filepaths_bad, labels)
  if do_shuffle:
    random.shuffle(entries)
  # Separate back into imgs / labels and return.
  imgs, labels = zip(*entries)
  return tf.constant(imgs), tf.constant(labels), len(labels), sum(labels)

def buildBothDatasets(img_paths, labels, train_test_split_percentage=0.8):
  # Split into training and test
  split = int(len(img_paths) * train_test_split_percentage)
  tr_imgs = tf.constant(img_paths[:split])
  tr_labels = tf.constant(labels[:split])
  val_imgs = tf.constant(img_paths[split:])
  val_labels = tf.constant(labels[split:])

  return tr_imgs, tr_labels, val_imgs, val_labels

def input_parser(img_path, label):
  # Read the img from file.
  img_file = tf.read_file(img_path)
  img_decoded = tf.image.decode_image(img_file, channels=1)

  return img_decoded, label

def randomize_image(img, contrast_range=[0.2,1.8], brightness_max=0.5):
  # Apply random flips/rotations and contrast/brightness changes to image
  img = tf.image.random_flip_left_right(img)
  img = tf.image.random_flip_up_down(img)
  img = tf.image.random_contrast(img, lower=contrast_range[0], upper=contrast_range[1])
  img = tf.image.random_brightness(img, max_delta=brightness_max)
  img = tf.contrib.image.rotate(img, tf.random_uniform([1], minval=-np.pi, maxval=np.pi))
  return img

def preprocessor(dataset, batch_size, dataset_length=None, is_training=False):
  if is_training and dataset_length:
    # Shuffle dataset.
    dataset = dataset.shuffle(dataset_length*2)

  # Load images from image paths.
  dataset = dataset.map(input_parser)

  if is_training:
    # Slightly randomize images.
    dataset = dataset.map(lambda img, label: (randomize_image(img), label))

  # Zero mean and unit normalize images, float image output.
  # TODO : Check if this needs to be applied to the predict function also
  # TODO : Does this cancel out random_brightness?
  # dataset = dataset.map(lambda img, label: (tf.image.per_image_standardization(img), label))
  
  # Bring down to 15x15 from 21x21
  dataset = dataset.map(lambda img, label: (tf.image.central_crop(img, 0.666666), label))

  # Batch and repeat.
  dataset = dataset.batch(batch_size)
  if is_training:
    dataset = dataset.repeat()

  return dataset

def input_fn(imgs, labels, dataset_length=None, is_training=False, batch_size=50):
  # Returns an appropriate input function for training/evaluation.
  def sub_input_fn():
    dataset = Dataset.from_tensor_slices((imgs, labels))
    # Pre-process dataset into correct form/batching/shuffle etc.
    dataset = preprocessor(dataset, batch_size, dataset_length, is_training)

    # Build iterator and return
    one_shot_iterator = dataset.make_one_shot_iterator()
    next_element = one_shot_iterator.get_next()

    # Return in a dict so the premade estimators can use it.
    return {"x": next_element[0]}, next_element[1]
  return sub_input_fn