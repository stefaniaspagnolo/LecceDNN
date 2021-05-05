### Reading from command line
from argparse import ArgumentParser

def ReadArgParser():
    parser = ArgumentParser()
    parser.add_argument('-a', '--Analysis', help = 'Type of analysis: \'merged\' or \'resolved\'', type = str)
    parser.add_argument('-c', '--Channel', help = 'Channel: \'ggF\' or \'VBF\'', type = str)
    parser.add_argument('-n', '--Nodes', help = 'Number of nodes of the (p)DNN, should always be >= nColumns and strictly positive', default = 32)
    parser.add_argument('-l', '--Layers', help = 'Number of layers of the (p)DNN', default = 2)
    parser.add_argument('-e', '--Epochs', help = 'Number of epochs for the training', default = 150)
    parser.add_argument('-v', '--Validation', help = 'Fraction of the training data that will actually be used for validation', default = 0.2)
    parser.add_argument('-d', '--Dropout', help = 'Fraction of the neurons to drop during the training', default = 0.2)
    
    args = parser.parse_args()
    
    analysis = args.Analysis
    if args.Analysis is None:
        parser.error('Requested type of analysis (either \'mergered\' or \'resolved\')')
    elif args.Analysis != 'resolved' and args.Analysis != 'merged':
        parser.error('Analysis can be either \'merged\' or \'resolved\'')
    channel = args.Channel
    if args.Channel is None:
        parser.error('Requested channel (either \'ggF\' or \'VBF\')')
    elif args.Channel != 'ggF' and args.Channel != 'VBF':
        parser.error('Channel can be either \'ggF\' or \'VBF\'')
    numberOfNodes = int(args.Nodes)
    if args.Nodes and numberOfNodes < 1:
        parser.error('Number of nodes must be strictly positive')
    numberOfLayers = int(args.Layers)
    if args.Layers and numberOfLayers < 1:
        parser.error('Number of layers must be strictly positive')
    numberOfEpochs = int(args.Epochs)
    if args.Epochs and numberOfEpochs < 1:
        parser.error('Number of epochs must be strictly positive')
    validationFraction = float(args.Validation)
    if args.Validation and (validationFraction < 0. or validationFraction > 1.):
        parser.error('Validation fraction must be between 0 and 1')
    dropout = float(args.Dropout)
    if args.Dropout and (dropout < 0. or dropout > 1.):
        parser.error('Dropout must be between 0 and 1')

    print('     nodes =', numberOfNodes)
    print('    layers =', numberOfLayers)
    print('    epochs =', numberOfEpochs)
    print('validation =', validationFraction)
    print('   dropout =', dropout)

    return dropout, analysis, channel, numberOfNodes, numberOfLayers, numberOfEpochs, validationFraction

### Reading from the configuration file
import configparser, ast

def ReadConfig(analysis):
    config = configparser.ConfigParser()
    config.read('Configuration.txt')
    dfPath = config.get('config', 'dfPath')
    modelPath = config.get('config', 'modelPath')
    if analysis == 'merged':
        InputFeatures = ast.literal_eval(config.get('config', 'inputFeaturesMerged'))
    elif analysis == 'resolved':
        InputFeatures = ast.literal_eval(config.get('config', 'inputFeaturesResolved'))
    return dfPath, modelPath, InputFeatures

### Checking if the output directory exists. If not, creating it
import os
from colorama import init, Fore
init(autoreset = True)

def checkCreateDir(dir):
    if not os.path.isdir(dir):
        os.makedirs(dir)
        return Fore.RED + ' (created)'
    else:
        return Fore.RED + ' (already there)'

### Loading data and creating input arrays
import pandas as pd

def LoadDataCreateArrays(dfPath, analysis, channel, InputFeatures):
    df_Train_path = dfPath + 'MixData_PD_' + analysis + '_' + channel + '_Train.pkl'
    df_Test_path = dfPath + 'MixData_PD_' + analysis + '_' + channel + '_Test.pkl'
    df_Train = pd.read_pickle(df_Train_path)
    df_Test = pd.read_pickle(df_Test_path)

    X_train = df_Train[InputFeatures].values
    y_train = df_Train['isSignal']
    w_train = df_Train['weight']
    
    X_test = df_Test[InputFeatures].values
    y_test = df_Test['isSignal']
    w_test = df_Test['weight']

    return X_train, y_train, X_test, y_test, df_Train_path, df_Test_path

### Shuffling data
import sklearn.utils

def ShufflingData(df):
    df = sklearn.utils.shuffle(df, random_state = 123)
#    df = df.reset_index(drop = True)
    return df

### Building the (p)DNN
from keras.models import Model, Sequential
from keras.layers import Dense, Dropout, Input, BatchNormalization
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers.core import Dense, Activation

def BuildDNN(N_input, width, depth, dropout):
    model = Sequential()
    model.add(Dense(units = width, input_dim = N_input))
    model.add(Activation('relu'))
    model.add(Dropout(dropout))
    for i in range(0, depth):
        model.add(Dense(width))
        model.add(Activation('relu'))
        model.add(Dropout(dropout))
    model.add(Dense(1, activation = 'sigmoid'))
    
    return model

import matplotlib
import matplotlib.pyplot as plt
plt.rcParams["figure.figsize"] = [7,7]
plt.rcParams.update({'font.size': 16})

### Evaluating the (p)DNN performance
def EvaluatePerformance(model, X_test, y_test):
    perf = model.evaluate(X_test, y_test, batch_size = 2048)
    testLoss = perf[0]
    testAccuracy = perf[1]
    print(format(Fore.BLUE + 'Test loss: ' + str(testLoss)))
    print(format(Fore.BLUE + 'Test  accuracy: ' + str(testAccuracy)))
    
    return testLoss, testAccuracy

### Saving the model
def SaveModel(model, outputDir):    
    model_yaml = model.to_yaml()
    modelFileName = outputDir + '/Higgs'    
    with open(modelFileName + '.yaml', 'w') as yaml_file:
        yaml_file.write(model_yaml)
    print('Saved ' + modelFileName + '.yaml')
    model.save_weights(modelFileName + '.h5')
    print('Saved ' + modelFileName + '.h5')

### Prediction on signal and background separately
def PredictionSigBkg(model, X_train_signal, X_train_bkg, X_test_signal, X_test_bkg):
    yhat_train_signal = model.predict(X_train_signal, batch_size = 2048)
    yhat_train_bkg = model.predict(X_train_bkg, batch_size = 2048)
    yhat_test_signal = model.predict(X_test_signal, batch_size = 2048)
    yhat_test_bkg = model.predict(X_test_bkg, batch_size = 2048)

    return yhat_train_signal, yhat_train_bkg, yhat_test_signal, yhat_test_bkg

### Drawing Accuracy
def DrawAccuracy(modelMetricsHistory, testAccuracy, outputDir, NN, mass = 0):
    plt.plot(modelMetricsHistory.history['accuracy'])
    plt.plot(modelMetricsHistory.history['val_accuracy'])
    titleAccuracy = 'Model accuracy'
    if NN == 'DNN':
        titleAccuracy = 'Model accuracy (mass: ' + str(int(mass)) + ')'
    plt.title(titleAccuracy)
    plt.ylabel('Accuracy')
    plt.xlabel('Epoch')
    plt.legend(['Training', 'Validation'], loc = 'lower right')
    plt.figtext(0.69, 0.28, 'Test accuracy: ' + str(round(testAccuracy, 3)), wrap = True, horizontalalignment = 'center')#, fontsize = 10)
    AccuracyPltName = outputDir + '/Accuracy.png'
    plt.savefig(AccuracyPltName)
    print('Saved ' + AccuracyPltName)
    plt.clf()

### Drawing Loss
def DrawLoss(modelMetricsHistory, testLoss, outputDir, NN, mass = 0):
    plt.plot(modelMetricsHistory.history['loss'])
    plt.plot(modelMetricsHistory.history['val_loss'])
    titleLoss = 'Model loss'
    if NN == 'DNN':
        titleLoss = 'Model loss (mass: ' + str(int(mass)) + ')'
    plt.title(titleLoss)
    plt.ylabel('Loss')
    plt.xlabel('Epoch')
    plt.legend(['Training', 'Validation'], loc = 'upper right')
    plt.figtext(0.7, 0.7, 'Test loss: ' + str(round(testLoss,2)), wrap = True, horizontalalignment = 'center')#, fontsize = 10)
    LossPltName = outputDir + '/Loss.png'
    plt.savefig(LossPltName)
    print('Saved ' + LossPltName)
    plt.clf()

### Drawing ROC (Receiver Operating Characteristic)
from sklearn.metrics import roc_curve, auc, roc_auc_score, classification_report
def DrawROC(fpr, tpr, outputDir, mass):
    plt.plot(fpr,  tpr, color = 'darkorange', lw = 2, label = 'Full curve')
    plt.plot([0, 0], [1, 1], color = 'navy', lw = 2, linestyle = '--')
    plt.xlim([-0.05, 1.0])
    plt.ylim([0.0, 1.05])
    plt.ylabel('True Positive Rate')
    plt.xlabel('False Positive Rate')
    titleROC = 'ROC curves (mass: ' + str(int(mass)) + ')'
    plt.title(titleROC)
    plt.legend(loc = 'lower right')
    ROCPltName = outputDir + '/ROC.png'
    plt.savefig(ROCPltName)
    print('Saved ' + ROCPltName)
    plt.clf()

### Drawing Scores
import numpy as np

def DrawScores(yhat_train_signal, yhat_test_signal, yhat_train_bkg, yhat_test_bkg, outputDir, NN, mass):
    bins = np.linspace(0, 1, 40)
    plt.hist(yhat_train_signal, bins = bins, histtype = 'step', lw = 2, color = 'blue', label = [r'Signal Train'], density = True)
    plt.hist(yhat_test_signal, bins = bins, histtype = 'stepfilled', lw = 2, color = 'cyan', alpha = 0.5, label = [r'Signal Test'], density = True)
    plt.hist(yhat_train_bkg, bins = bins, histtype = 'step', lw = 2, color = 'red', label = [r'Background Train'], density = True)
    plt.hist(yhat_test_bkg, bins = bins, histtype = 'stepfilled', lw = 2, color = 'orange', alpha = 0.5, label = [r'Background Test'], density = True)
    plt.ylabel('Norm. Entries')
    plt.xlabel(NN + ' score')
    titleScores = 'Scores (mass: ' + str(int(mass)) + ')'
    plt.title(titleScores)
    plt.legend(loc = 'upper center')
    ScoresPltName = outputDir + '/Scores.png'
    plt.savefig(ScoresPltName)
    print('Saved ' + ScoresPltName)
    plt.clf()

### Confusion matrix
from sklearn.metrics import confusion_matrix
import itertools

def DrawCM(yhat_test, y_test, normalize, outputDir, mass):
    yResult_test_cls = np.array([ int(round(x[0])) for x in yhat_test])
    cm = confusion_matrix(y_test, yResult_test_cls)
    classes = ['Background', 'Signal']
    np.set_printoptions(precision = 2)
    if normalize:
        cm = cm.astype('float') / cm.sum(axis = 1)[:, np.newaxis]
    cmap = plt.cm.Oranges#Blues
    plt.imshow(cm, interpolation = 'nearest', cmap = cmap)
    titleCM = 'Confusion matrix (Mass: ' + str(int(mass)) + ')'
    plt.title(titleCM)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes)
    plt.yticks(tick_marks, classes, rotation = 90)
    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt), horizontalalignment = "center", color = "white" if cm[i, j] > thresh else "black")
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    CMPltName = outputDir + '/ConfusionMatrix.png'
    plt.savefig(CMPltName)
    #plt.show()
    print('Saved ' + CMPltName)
    plt.clf()    

### Number of events in signal samples = number of events in bkg samples
def EventsCut(XTrainSignal, XTrainBkg, XTestSignal, XTestBkg):
    if XTrainSignal.shape[0] > XTrainBkg.shape[0]:
        NeventsTrain = XTrainBkg.shape[0]
        print(format(Fore.RED + 'Number of train signal events (' + str(XTrainSignal.shape[0]) + ') higher than number of train background events (' + str(XTrainBkg.shape[0]) + ') -> using '+ str(NeventsTrain) + ' events'))
        XTrainSignal = XTrainSignal[:NeventsTrain]
    else:
        NeventsTrain = XTrainSignal.shape[0]
        print(format(Fore.RED + 'Number of train background events (' + str(XTrainBkg.shape[0]) + ') higher than number of train signal events (' + str(XTrainSignal.shape[0]) + ') -> using ' + str(NeventsTrain) + ' events'))
        XTrainBkg = XTrainBkg[:NeventsTrain]
    if XTestSignal.shape[0] > XTestBkg.shape[0]:
        NeventsTest = XTestBkg.shape[0]
        print(format(Fore.RED + 'Number of test signal events (' + str(XTestSignal.shape[0]) + ') higher than number of test background events (' + str(XTestBkg.shape[0]) + ') -> using '+ str(NeventsTest) + ' events'))
        XTestSignal = XTestSignal[:NeventsTest]
    else:
        NeventsTest = XTestSignal.shape[0]
        print(format(Fore.RED + 'Number of test background events (' + str(XTestBkg.shape[0]) + ') higher than number of test signal events (' + str(XTestSignal.shape[0]) + ') -> using ' + str(NeventsTest) + ' events'))
        XTestBkg = XTestBkg[:NeventsTest]
    return XTrainSignal, XTrainBkg, XTestSignal, XTestBkg

def EventsWeight(XTrainSignal, XTrainBkg):

    if XTrainSignal.shape[0] > XTrainBkg.shape[0]:
        WTrainSignal = XTrainBkg.shape[0] / XTrainSignal.shape[0]       
        WTrainBkg = 1
    else:
        WTrainBkg = XTrainSignal.shape[0] / XTrainBkg.shape[0]       
        WTrainSignal = 1

    return WTrainSignal, WTrainBkg