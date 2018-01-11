# DCGAN to be trained on CelebA with no labels and have params stored
import sys
sys.path.append('../')

from dataload import CELEBA
from utils import make_new_folder, plot_norm_losses, save_input_args, \
sample_z, class_loss_fn, plot_losses, corrupt # one_hot
from models import GEN, DIS


import torch
from torch import optim
from torch import nn
from torch.autograd import Variable
import torch.nn.functional as F
from torch.nn.functional import binary_cross_entropy as bce

from torchvision import transforms
from torchvision.utils import make_grid, save_image

import numpy as np

import os
from os.path import join

import argparse

from PIL import Image

import matplotlib 
matplotlib.use('Agg')
from matplotlib import pyplot as plt

from time import time

EPSILON = 1e-6

def get_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('--root', default='../../../../data/', type=str)
	parser.add_argument('--batchSize', default=64, type=int)
	parser.add_argument('--maxEpochs', default=10, type=int)
	parser.add_argument('--nz', default=100, type=int)
	parser.add_argument('--lr', default=1e-3, type=float)
	parser.add_argument('--fSize', default=64, type=int)  #multiple of filters to use
	parser.add_argument('--outDir', default='../../Experiments/', type=str)
	parser.add_argument('--commit', required=True, type=str)
	parser.add_argument('--gpuNo', default=0, type=int)

	return parser.parse_args()


def train_mode(gen, dis):
	####### Define optimizer #######
	genOptimizer = optim.Adam(gen.parameters(), lr=opts.lr)
	disOptimizer = optim.SGD(dis.parameters(), lr=opts.lr)

	if gen.useCUDA:
		torch.cuda.set_device(opts.gpuNo)
		gen.cuda()
		dis.cuda()
	
	####### Create a new folder to save results and model info #######
	exDir = make_new_folder(opts.outDir)
	print 'Outputs will be saved to:',exDir
	save_input_args(exDir, opts)

	####### Start Training #######
	losses = {'gen':[], 'dis':[]}
	for e in range(opts.maxEpochs):
		dis.train()
		gen.train()

		epochLoss_gen = 0
		epochLoss_dis = 0

		T = time()
		for i, data in enumerate(trainLoader, 0):

			# add a small amount of corruption to the data
			xReal = Variable(data[0])
			if gen.useCUDA:
				xReal = xReal.cuda()


			####### Calculate discriminator loss #######
			noSamples = xReal.size(0)
			xFake = gen.sample_x(noSamples)
			pReal_D = dis.forward(xReal)
			pFake_D = dis.forward(xFake.detach())

			real = dis.ones(xReal.size(0))
			fake = dis.zeros(xFake.size(0))

			disLoss = 0.5 * (F.binary_cross_entropy(pReal_D, real) + \
						F.binary_cross_entropy(pFake_D, fake))

			####### Calculate generator loss #######
			xFake_ = gen.sample_x(noSamples)
			pFake_G = dis.forward(xFake_)
			genLoss = F.binary_cross_entropy(pFake_G, real)

			####### Do DIS updates #######
			disOptimizer.zero_grad()
			disLoss.backward()
			disOptimizer.step()

			####### Do GEN updates #######
			genOptimizer.zero_grad()
			genLoss.backward()
			genOptimizer.step()

			losses['gen'].append(genLoss.data[0])
			losses['dis'].append(disLoss.data[0])

			####### Print info #######
			if i%100==1:
				print '[%d, %d] gen: %.5f, dis: %.5f, time: %.2f' \
					% (e, i, epochLoss_gen/i, epochLoss_dis/i, time()-T)

		
		print '[%d, %d] gen: %.5f, dis: %.5f, time: %.2f' \
				% (e, i, epochLoss_gen/i, epochLoss_dis/i, time()-T)

		####### Tests #######
		gen.eval()
		print 'Outputs will be saved to:',exDir
		#save some samples
		samples = gen.sample_x(49)
		save_image(samples.data, join(exDir,'epoch'+str(e)+'.png'))

		#plot
		plot_losses(losses, exDir)

		####### Save params #######
		gen.save_params(exDir)
		dis.save_params(exDir)

	return gen, dis



if __name__=='__main__':
	opts = get_args()

	####### Data set #######
	print 'Prepare data loaders...'
	transform = transforms.Compose([transforms.ToTensor(), \
		transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)), transforms.RandomHorizontalFlip()])
	trainDataset = CELEBA(root=opts.root, train=True, transform=transforms.ToTensor())
	trainLoader = torch.utils.data.DataLoader(trainDataset, batch_size=opts.batchSize, shuffle=True)

	transform = transforms.Compose([transforms.ToTensor(), \
		transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
	testDataset = CELEBA(root=opts.root, train=False, transform=transform)
	testLoader = torch.utils.data.DataLoader(testDataset, batch_size=opts.batchSize, shuffle=False)
	print 'Data loaders ready.'

	###### Create model #####
	IM_SIZE = 64

	gen = GEN(imSize=IM_SIZE, nz=opts.nz, fSize=opts.fSize)
	dis = DIS (imSize=IM_SIZE, fSize=opts.fSize)

	gen, dis = train_mode(gen, dis)

