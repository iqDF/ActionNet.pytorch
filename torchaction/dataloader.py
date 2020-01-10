import nvidia
import nvidia.dali.ops as ops
import nvidia.dali.types as types
from nvidia.dali.pipeline import Pipeline
from nvidia.dali.plugin.pytorch import DALIGenericIterator


class VideoReaderPipeline(Pipeline):
    """ Pipeline for reading H264 videos based on NVIDIA DALI.
	Returns a batch of sequences of `sequence_length` frames of shape [N, F, C, H, W]
	(N being the batch size and F the number of frames). Frames are RGB uint8.
    
    Arguments:
    ------------------------------
		.. file_root (str):
				Video root directory which has been structured as standard labelled video dir
		.. batch_size (int):
				Size of batches
		.. sequence_length (int):
				Length of video clip, the time dimension
		.. crop_size (int or list of int):
				Size of the cropped frame/image as H x W
		.. num_threads (int):
				Number of threads spawned for loading video
		.. device_id (int):
				Gpu device id to be used
		.. output_layout (str, optional):
				Layout dimension of the output frames. Default to [N, C, H, W]
		.. random_shuffle (bool, optional):
				Whether to random shuffle data
		.. step (int, optional):
				Frame interval between each sequence (if `step` < 0, `step` is set to `sequence_length`).
    """

    def __init__(self, file_root, batch_size, sequence_length, crop_size, 
				num_threads, device_id, output_layout=types.NCHW,
				random_shuffle=True, step=-1):
		super().__init__(batch_size, num_threads, device_id, seed=42)

		# Define video reader
		self.reader = ops.VideoReader(device = "gpu",
										file_root = file_root,
										sequence_length = sequence_length,
										normalized = False,
										random_shuffle = random_shuffle,
										image_type = types.RGB,
										dtype = types.UINT8,
										step = step,
										initial_fill = 16)

		self.rescrop = ops.RandomResizedCrop(device = "gpu",
												seed = seed,
												size = crop_size,
												random_area = [0.8, 1.0],
												random_aspect_ratio = [1.0, 1.0])
		
		self.transpose = ops.Transpose(device = "gpu",
										seed = seed,
										output_layout = types.NCHW)

	def define_graph(self):
		""" Definition of graph-event that defines flow of video pipeline
		"""
		input_vid  = self.reader(name = "Reader")
		rescropped = self.rescrop(input_vid)
		output_vid = self.transpose(rescropped)

		return output_vid


class VideoLoader:
	""" Wrapper to DALI Pipeline + DALI Generic Iterator
	
	Arguments
	-----------------------------
		.. file_root (str):
				Path to video root directory which has been structured as standard labelled video dir
		.. batch_size (int):
				Size of batches
		.. sequence_length (int):
				Length of video clip, the time dimension
		.. crop_size (int or list of int):
				Size of the cropped frame/image as H x W
		.. num_threads (int):
				Number of threads spawned for loading video
		.. device_id (int):
				Gpu device id to be used
		.. random_shuffle (bool, optional):
				Whether to shuffle video randomly
		.. epoch_size (int, optional):
				Size of the epoch, if epoch_size <= 0, epoch_size will default to the size of VideoReaderPipeline
		.. temp_stride (int, optional):
				Frame interval between each sequence
				(if `temp_stride` < 0, `temp_stride` is set to `sequence_length`).
	"""

	def __init__(self, file_root, batch_size, sequence_length, crop_size,
				random_shuffle=True, epoch_size=-1, temp_stride=-1):

		# Define video reader pipeline
		self.pipeline = VideoReaderPipeline(file_root = file_root, 
											batch_size = batch_size,
											sequence_length = sequence_length,
											crop_size = crop_size,
											num_threads = 2,
											device_id = 1,
											output_layout = types.NCHW,
											random_shuffle = random_shuffle,
											step = temp_stride)
		# Build pipeline
		self.pipeline.build()

		# Define epoch size
		if epoch_size <= 0:
			self.epoch_size = self.pipeline.epoch_size("Reader")
		else:
			self.epoch_size = epoch_size

		# Define DALI iterator
		self.dali_iterator = DALIGenericIterator(self.pipeline,
												output_map = ["data", "label"],
												size = self.epoch_size,
												auto_reset = True)

	def __len__(self):
		return self.epoch_size

	def __iter__(self):
		retur self.dali_iterator.__iter__()
