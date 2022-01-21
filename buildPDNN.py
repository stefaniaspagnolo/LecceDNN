from Functions import *
import time
#start = time.time()
### Setting a seed for reproducibility
tf.random.set_seed(1234)

NN = 'PDNN'
batchSize = 2048

### Reading the command line
tag, jetCollection, analysis, channel, preselectionCuts, background, trainingFraction, signal, numberOfNodes, numberOfLayers, numberOfEpochs, validationFraction, dropout, testMass, doTrain, doTest, loop = ReadArgParser()

originsBkgTest = list(background.split('_'))

### Reading the configuration file
ntuplePath, dfPath, InputFeatures = ReadConfig(tag, analysis, jetCollection)
dfPath += analysis + '/' + channel + '/' + signal + '/' + background + '/'
outputFileCommonName = jetCollection + '_' + analysis + '_' + channel + '_' + preselectionCuts + '_' + signal + '_' + background + '_' + NN

### Creating the output directory and the logFile
outputDir = dfPath + NN + '_fullStat'
print(format('Output directory: ' + Fore.GREEN + outputDir), checkCreateDir(outputDir))
logFileName = outputDir + '/logFile_' + outputFileCommonName + '.txt'
logFile = open(logFileName, 'w')
logInfo = ''
logString = WriteLogFile(tag, ntuplePath, numberOfNodes, numberOfLayers, numberOfEpochs, validationFraction, dropout, InputFeatures, dfPath)
logFile.write(logString)
logInfo += logString

### Loading input data
data_train, data_test, X_train_unscaled, m_train_unscaled, m_test_unscaled = LoadData(dfPath, jetCollection, signal, analysis, channel, background, trainingFraction, preselectionCuts, InputFeatures)

### Extracting X and y arrays 
X_train = np.array(data_train[InputFeatures].values).astype(np.float32)
y_train = np.array(data_train['isSignal'].values).astype(np.float32)
X_test = np.array(data_test[InputFeatures].values).astype(np.float32)
y_test = np.array(data_test['isSignal'].values).astype(np.float32)

### Writing dataframes composition to the log file
logString = '\nNumber of train events: ' + str(len(X_train)) + ' (' + str(int(sum(y_train))) + ' signal and ' + str(int(len(y_train) - sum(y_train))) + ' background)' + '\nNumber of test events: ' + str(len(X_test)) + ' (' + str(int(sum(y_test))) + ' signal and ' + str(int(len(y_test) - sum(y_test))) + ' background)'
bkgNumber = int(len(y_test) - sum(y_test))
logFile.write(logString)
logInfo += logString

### Weighting train events
origin_train = np.array(data_train['origin'].values)
w_train, origins_list, DictNumbers, DictWeights = weightEvents(origin_train, str(signal))
logString = '\nOrigin list: ' + str(origins_list) + '\nOrigins numbers: ' + str(DictNumbers) + '\nOrigins weights: ' + str(DictWeights)
logFile.write(logString)
logInfo += logString

bkgRejFile = open(outputDir + '/BkgRejectionOldROC.txt', 'w')
#bkgRejFile.write('Background rejection obtained using...')
bkgRej90 = []
bkgRej94 = []
bkgRej97 = []
bkgRej99 = []

for i in range(loop):

    #print(Fore.RED + 'loop: ' + str(i))
    ### Building and compiling the PDNN
    model, Loss, Metrics, learningRate, Optimizer = BuildDNN(len(InputFeatures), numberOfNodes, numberOfLayers, dropout) 
    model.compile(loss = Loss, optimizer = Optimizer, weighted_metrics = Metrics)
    logString = '\nLoss: ' + Loss + '\nLearning rate: ' + str(learningRate) + '\nOptimizer: ' + str(Optimizer) + '\nweighted_metrics: ' + str(Metrics)
    logFile.write(logString)
    logInfo += logString
    
    if doTrain == False:
        from keras.models import model_from_json
        print(Fore.BLUE + 'Loading architecture and weights')
        architectureFile = open(outputDir + '/architecture.json', 'r')
        loadedModel = architectureFile.read()
        architectureFile.close()
        print(Fore.GREEN + 'Loaded ' + outputDir + '/achitecture.json') 
        model = model_from_json(loadedModel)
        model.load_weights(outputDir + '/weights.h5')
        print(Fore.GREEN + 'Loaded ' + outputDir + '/weights.h5')

    if doTrain == True:
        ### Training
        patienceValue = 5
        print(Fore.BLUE + 'Training the ' + NN)
        modelMetricsHistory = model.fit(X_train, y_train, sample_weight = w_train, epochs = numberOfEpochs, batch_size = batchSize, validation_split = validationFraction, verbose = 1, shuffle = False, callbacks = EarlyStopping(verbose = True, patience = patienceValue, monitor = 'val_loss', restore_best_weights = True))

        ### Saving to files
        SaveModel(model, X_train_unscaled, outputDir)
        
        if doTest == True:
            ### Evaluating the performance of the PDNN on the test sample and writing results to the log file
            print(Fore.BLUE + 'Evaluating the performance of the ' + NN)
            testLoss, testAccuracy = EvaluatePerformance(model, X_test, y_test, batchSize)
            logString = '\nTest loss: ' + str(testLoss) + '\nTest accuracy: ' + str(testAccuracy)
            logFile.write(logString)
            logInfo += logString
            
        else:
            testLoss = testAccuracy = None
            ### Drawing accuracy and loss
            DrawLoss(modelMetricsHistory, testLoss, patienceValue, outputDir, NN, jetCollection, analysis, channel, preselectionCuts, signal, background, outputFileCommonName)
            DrawAccuracy(modelMetricsHistory, testAccuracy, patienceValue, outputDir, NN, jetCollection, analysis, channel, preselectionCuts, signal, background, outputFileCommonName)

    logFile.close()
    print(Fore.GREEN + 'Saved ' + logFileName)

    if doTest == False:
        exit()

    ### Dividing signal from background
    data_test_signal = data_test[y_test == 1]
    data_test_bkg = data_test[y_test != 1]
    X_train_signal = X_train[y_train == 1]
    X_train_bkg = X_train[y_train != 1]

    ### Saving unscaled test signal mass values
    m_test_unscaled_signal = m_test_unscaled[y_test == 1]
    unscaledTestMassPointsList = list(dict.fromkeys(list(m_test_unscaled_signal)))
    
    ### Saving scaled test signal mass values
    m_test_signal = data_test_signal['mass']
    scaledTestMassPointsList = list(dict.fromkeys(list(m_test_signal)))
    
    ### If testMass = 'all', defining testMass as the list of test signal masses 
    if testMass == ['all']:
        testMass = list(int(item) for item in set(list(m_test_unscaled_signal)))
        testMass.sort()

    for unscaledMass in testMass:
        unscaledMass = int(unscaledMass)

        ### Checking whether there are train events with the selected mass
        if unscaledMass not in unscaledTestMassPointsList:
            print(Fore.RED + 'No test signal with mass ' + str(unscaledMass))
            continue

        ### Associating the unscaled mass to the scaled one
        mass = scaledTestMassPointsList[unscaledTestMassPointsList.index(unscaledMass)]
        
        ### Creating new output directory and log file
        newOutputDir = outputDir + '/' + str(int(unscaledMass))
        print(format('Output directory: ' + Fore.GREEN + newOutputDir), checkCreateDir(newOutputDir))
        newLogFileName = newOutputDir + '/logFile_' + outputFileCommonName + '_' + str(unscaledMass) + '.txt'
        newLogFile = open(newLogFileName, 'w')

        ### Selecting only test signal events with the same mass value and saving them as an array
        data_test_signal_mass = data_test_signal[m_test_signal == mass]
        X_test_signal_mass = np.asarray(data_test_signal_mass[InputFeatures].values).astype(np.float32)
        newLogFile.write(logInfo + '\nNumber of test signal events with mass ' + str(int(unscaledMass)) + ' GeV: ' + str(len(X_test_signal_mass)))
        
        ### Assigning the same mass value to test background events and saving them as an array
        data_test_bkg = data_test_bkg.assign(mass = np.full(len(data_test_bkg), mass))
        X_test_bkg = np.asarray(data_test_bkg[InputFeatures].values).astype(np.float32)
        
        ### Selecting train signal events with the same mass
        m_train_signal = X_train_signal[:, InputFeatures.index('mass')]
        X_train_signal_mass = X_train_signal[m_train_signal == mass]

        ### Assigning the same mass value to train background events
        X_train_bkg[:, InputFeatures.index('mass')] = np.full(len(X_train_bkg), mass)
        
        ### Prediction on signal and background
        yhat_train_signal_mass, yhat_train_bkg_mass, yhat_test_signal_mass, yhat_test_bkg_mass = PredictionSigBkg(model, X_train_signal_mass, X_train_bkg, X_test_signal_mass, X_test_bkg, batchSize)

        ### Drawing confusion matrix
        yhat_test_mass = np.concatenate((yhat_test_signal_mass, yhat_test_bkg_mass))
        y_test_mass = np.concatenate((np.ones(len(yhat_test_signal_mass)), np.zeros(len(yhat_test_bkg_mass))))

        TNR, FPR, FNR, TPR = DrawCM(yhat_test_mass, y_test_mass, newOutputDir, unscaledMass, background, outputFileCommonName, jetCollection, analysis, channel, preselectionCuts, signal)
        newLogFile.write('\TNR (TN/N): ' + str(TNR) + '\nFPR (FP/N): ' + str(FPR) + '\FNR (FN/P): ' + str(FNR) + '\n TPR (TP/P): ' + str(TPR))

        ### Computing ROC AUC
        fpr, tpr, thresholds = roc_curve(y_test_mass, yhat_test_mass)
        roc_auc = auc(fpr, tpr)
        print(format(Fore.BLUE + 'ROC_AUC: ' + str(roc_auc)))
        newLogFile.write('\nROC_AUC: ' + str(roc_auc))

        ### Plotting ROC, background rejection and scores
        WP, bkgRejWP = DrawROCbkgRejectionScores(fpr, tpr, roc_auc, newOutputDir, NN, unscaledMass, jetCollection, analysis, channel, preselectionCuts, signal, background, outputFileCommonName, bkgNumber, yhat_train_signal_mass, yhat_test_signal_mass, yhat_train_bkg_mass, yhat_test_bkg_mass)
        newLogFile.write('\nWorking points: ' + str(WP) + '\nBackground rejection at each working point: ' + str(bkgRejWP))

        bkgRej90.append(bkgRejWP[0])
        bkgRej94.append(bkgRejWP[1])
        bkgRej97.append(bkgRejWP[2])
        bkgRej99.append(bkgRejWP[3])
        
        ### Closing the newLogFile
        newLogFile.close()
        print(Fore.GREEN + 'Saved ' + newLogFileName)
        '''
        if i == (loop - 1):
            newbkgRejFile.close()
        '''
    if (len(testMass) > 1):
        DrawRejectionVsMass(testMass, WP, bkgRej90, bkgRej94, bkgRej97, bkgRej99, outputDir, jetCollection, analysis, channel, preselectionCuts, signal, background, outputFileCommonName) 

'''
end = time.time()
print("The time of execution of above program is :", end-start)
'''
