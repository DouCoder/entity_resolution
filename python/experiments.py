__author__ = 'mbarnes1'
from database import Database, SyntheticDatabase
from copy import deepcopy
from entityresolution import EntityResolution
from pairwise_features import generate_pair_seed
from itertools import izip
import numpy as np
from metrics import Metrics, _cluster
import matplotlib.pyplot as plt
plt.ion()
from matplotlib.widgets import Slider
import cProfile
import matplotlib.cm as cm
from new_metrics import NewMetrics
import cPickle as pickle

# Color-blind safe color palette
# Blue: #4477AA
# Tan: #DDCC77
# Magenta: #CC6677


class SyntheticExperiment(object):
    class ResultsPlot(object):
        """
        2D plot of all the entities and logistic regression decision boundaries (ellipsoids)
        """
        def __init__(self, experiment):
            """
            :param experiment: SyntheticExperiment parent object
            """
            self._experiment = experiment
            color_seed = cm.rainbow(np.linspace(0, 1, len(experiment.uncorrupted_synthetic_test.labels)))
            np.random.shuffle(color_seed)
            self._color_seed = color_seed  # np.random.rand(len(experiment._uncorrupted_synthetic_test.labels))

            self._corruption_index = 0
            self._threshold_index = 0

            # Plot the metrics
            self._figures = list()
            self._axes = list()

            # ER Precision/Recall Lower Bound Debugging
            fig = plt.figure()
            self._figures.append(fig)
            ax = fig.add_subplot(111)
            #self._axes.append(ax)
            TP_FP_match = list()  # TP_match + FP_match
            TP_FP_swoosh = list()  # TP_swoosh + FP_swoosh
            for threshold_index, threshold in enumerate(experiment.thresholds):
                TP_FP_match.append(experiment.new_metrics[self._corruption_index][threshold_index].TP_FP_match)
                TP_FP_swoosh.append(experiment.new_metrics[self._corruption_index][threshold_index].TP_FP_swoosh)
            self.TP_FP_match, = ax.plot(experiment.thresholds, TP_FP_match, label='TP + FP, match', linewidth=2, color='g')
            self.TP_FP_swoosh, = ax.plot(experiment.thresholds, TP_FP_swoosh, label='TP + FP, swoosh', linewidth=2, color='r', linestyle='--')
            plt.legend(loc='upper left')
            ax.set_xlabel('Threshold')
            ax.set_ylabel('Count')
            ax.set_title('Lower Bound Debugging')


            # Match function precision recall curve
            fig = plt.figure()
            self._figures.append(fig)
            ax = fig.add_subplot(111)
            self._axes.append(ax)
            match_thresholds = experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.prob
            match_precision = experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.precision  # threshold index should be arbitrary
            match_recall = experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.recall  # threshold index should be arbitrary
            match_f1 = experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.f1  # threshold index should be arbitrary
            self.match_precision, = ax.plot(match_thresholds, match_precision, label='Precision', linewidth=2, color='#4477AA')  # blue
            self.match_recall, = ax.plot(match_thresholds, match_recall, label='Recall', linewidth=2, color='#CC6677')  # Magenta
            self.match_f1, = ax.plot(match_thresholds, match_f1, label='F1', linewidth=2, color='#DDCC77')  # Tan
            plt.legend(loc='upper left')
            ax.set_xlabel('Threshold')
            ax.set_ylabel('Score')
            ax.set_title('Match Function Performance')
            ax.set_xlim([0, 1.0])
            ax.set_ylim([0, 1.0])

            # Pairwise F1
            fig = plt.figure()
            self._figures.append(fig)
            ax = fig.add_subplot(111)
            #ax.grid(linestyle='--')
            self._axes.append([ax])
            pairwise_f1 = list()
            pairwise_f1_lower_bound = list()
            pairwise_precision = list()
            pairwise_precision_lower_bound = list()
            pairwise_recall = list()
            pairwise_recall_lower_bound = list()
            for threshold_index, threshold in enumerate(experiment.thresholds):
                pairwise_f1.append(experiment.metrics[self._corruption_index][threshold_index].pairwise_f1)
                pairwise_precision.append(experiment.metrics[self._corruption_index][threshold_index].pairwise_precision)
                pairwise_recall.append(experiment.metrics[self._corruption_index][threshold_index].pairwise_recall)
                pairwise_precision_lower_bound.append(experiment.new_metrics[self._corruption_index][threshold_index].precision_lower_bound)
                pairwise_recall_lower_bound.append(experiment.new_metrics[self._corruption_index][threshold_index].recall_lower_bound)
                pairwise_f1_lower_bound.append(experiment.new_metrics[self._corruption_index][threshold_index].f1_lower_bound)
            self.pf1, = ax.plot(experiment.thresholds, pairwise_f1, label='F1', linewidth=2, color='#DDCC77', linestyle='--')
            self.pp, = ax.plot(experiment.thresholds, pairwise_precision, label='Precision', linewidth=2, color='#4477AA', linestyle='--')
            self.pr, = ax.plot(experiment.thresholds, pairwise_recall, label='Recall', linewidth=2, color='#CC6677', linestyle='--')
            #self.pf1_dot, = ax.plot(experiment.thresholds[self._threshold_index], pairwise_f1[self._threshold_index],
            #                        'bo', markersize=10, label='Operating Point')
            self.pf1_lower, = ax.plot(experiment.thresholds, pairwise_f1_lower_bound, label='F1 Lower Bound', linewidth=2, color='#DDCC77')
            self.pp_lower, = ax.plot(experiment.thresholds, pairwise_precision_lower_bound, label='Precision Lower Bound', linewidth=2, color='#4477AA')
            self.pr_lower, = ax.plot(experiment.thresholds, pairwise_recall_lower_bound, label='Recall Lower Bound', linewidth=2, color='#CC6677')
            plt.legend(loc='upper left')
            self._axes[1][0].set_xlabel('Threshold')
            self._axes[1][0].set_ylabel('Pairwise Metric')
            self._axes[1][0].set_title('Pairwise Metrics')
            self._axes[1][0].set_ylim([0, 1.0])

            # New metric
            # fig = plt.figure()
            # self._figures.append(fig)
            # ax = fig.add_subplot(111)
            # ax.grid(linestyle='--')
            # self._axes.append([ax])
            # new_metrics_expected = list()
            # new_metrics_best = list()
            # new_metrics_worst = list()
            # for threshold_index, threshold in enumerate(experiment.thresholds):
            #     new_metrics_expected.append(-1*experiment.new_metrics[self._corruption_index][threshold_index].net_expected_cost)
            #     new_metrics_best.append(-1*experiment.new_metrics[self._corruption_index][threshold_index].greedy_best_cost)
            #     new_metrics_worst.append(-1*experiment.new_metrics[self._corruption_index][threshold_index].greedy_worst_cost)
            # self.new_metrics_expected, = ax.plot(experiment.thresholds, new_metrics_expected, label='Expected')
            # self.new_metrics_best, = ax.plot(experiment.thresholds, new_metrics_best, label='Upper Greedy Bound')
            # self.new_metrics_worst, = ax.plot(experiment.thresholds, new_metrics_worst, label='Lower Greedy Bound')
            # plt.legend(handles=[self.new_metrics_expected, self.new_metrics_best, self.new_metrics_worst], loc='upper left')
            # # self.new_metrics_dot, = ax.plot(experiment.thresholds[self._threshold_index],
            # #                                 new_metrics_expected[self._threshold_index], 'bo', markersize=10,
            # #                                 label='Operating Point')
            # self._axes[2][0].set_xlabel('Threshold')
            # self._axes[2][0].set_ylabel('-New Metric')
            # self._axes[2][0].set_title('New Metric - Path Costs')

            # Plot the samples
            self._figures.append(plt.figure())
            ax0 = self._figures[-1].add_subplot(121, aspect='equal')
            ax1 = self._figures[-1].add_subplot(122, aspect='equal')
            self._axes.append([ax0, ax1])
            plt.subplots_adjust(bottom=0.25)  # changes location of plot's bottom left hand corner (no slider overlap)

            # plot ground truth
            true_labels = experiment.uncorrupted_synthetic_test.labels
            experiment.synthetic_test[self._corruption_index].plot(true_labels, title='True Clustering',
                                                                   color_seed=self._color_seed, ax=self._axes[-1][0])

            # plot predicted cluster
            predicted_labels = experiment.predicted_labels[self._corruption_index][self._threshold_index]
            experiment.synthetic_test[self._corruption_index].plot(predicted_labels, title='Predicted Clustering',
                                                                   color_seed=self._color_seed, ax=self._axes[-1][1])

            # make the sliders
            axframe = plt.axes([0.125, 0.1, 0.775, 0.03])
            self.sframe = Slider(axframe, 'Noise', 0, len(experiment.corruption_multipliers)-1, valinit=0, valfmt='%d')
            axframe2 = plt.axes([0.125, 0.15, 0.775, 0.03])
            self.sframe2 = Slider(axframe2, 'Threshold', 0, len(experiment.thresholds)-1, valinit=0, valfmt='%d')

            # connect callback to slider
            self.sframe.on_changed(self.update)
            self.sframe2.on_changed(self.update2)
            plt.show()

        # call back function
        def update(self, _):
            """
            Updating the corruption
            """
            corruption_index = int(np.floor(self.sframe.val))
            if corruption_index != self._corruption_index:
                true_labels = self._experiment.uncorrupted_synthetic_test.labels
                predicted_labels = self._experiment.predicted_labels[corruption_index][self._threshold_index]
                self._axes[-1][0].clear()
                self._axes[-1][1].clear()
                self._experiment.synthetic_test[corruption_index].plot(true_labels, title='True Clustering',
                                                                       color_seed=self._color_seed, ax=self._axes[-1][0])
                self._experiment.synthetic_test[corruption_index].plot(predicted_labels, title='Predicted Clustering',
                                                                       color_seed=self._color_seed, ax=self._axes[-1][1])
                # new_metrics_expected = list()
                # new_metrics_best = list()
                # new_metrics_worst = list()
                pairwise_f1 = list()
                pairwise_f1_lower_bound = list()
                pairwise_precision = list()
                pairwise_precision_lower_bound = list()
                pairwise_recall = list()
                pairwise_recall_lower_bound = list()
                match_precision = self._experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.precision
                match_recall = self._experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.recall
                match_f1 = self._experiment.er[self._corruption_index][self._threshold_index]._match_function.roc.f1
                for threshold_index, threshold in enumerate(self._experiment.thresholds):
                    pairwise_f1.append(self._experiment.metrics[self._corruption_index][threshold_index].pairwise_f1)
                    pairwise_precision.append(self._experiment.metrics[self._corruption_index][threshold_index].pairwise_precision)
                    pairwise_recall.append(self._experiment.metrics[self._corruption_index][threshold_index].pairwise_recall)
                    pairwise_precision_lower_bound.append(self._experiment.new_metrics[self._corruption_index][threshold_index].precision_lower_bound)
                    pairwise_recall_lower_bound.append(self._experiment.new_metrics[self._corruption_index][threshold_index].recall_lower_bound)
                    pairwise_f1_lower_bound.append(self._experiment.new_metrics[self._corruption_index][threshold_index].f1_lower_bound)
                    # new_metrics_expected.append(-1*self._experiment.new_metrics[self._corruption_index][threshold_index].net_expected_cost)
                    # new_metrics_best.append(-1*self._experiment.new_metrics[self._corruption_index][threshold_index].greedy_best_cost)
                    # new_metrics_worst.append(-1*self._experiment.new_metrics[self._corruption_index][threshold_index].greedy_worst_cost)
                self.match_precision.set_ydata(match_precision)
                self.match_recall.set_ydata(match_recall)
                self.match_f1.set_ydata(match_f1)
                self.pf1.set_ydata(pairwise_f1)
                self.pf1_lower.set_ydata(pairwise_f1_lower_bound)
                self.pp.set_ydata(pairwise_precision)
                self.pp_lower.set_ydata(pairwise_precision_lower_bound)
                self.pr.set_ydata(pairwise_recall)
                self.pr_lower.set_ydata(pairwise_recall_lower_bound)
                #self.pf1_dot.set_ydata(pairwise_f1[self._threshold_index])
                # self.new_metrics_expected.set_ydata(new_metrics_expected)
                # self.new_metrics_best.set_ydata(new_metrics_best)
                # self.new_metrics_worst.set_ydata(new_metrics_worst)
                #self.new_metrics_dot.set_ydata(new_metrics[self._threshold_index])
                for figure in self._figures:
                    figure.canvas.draw()
                self._corruption_index = corruption_index

        def update2(self, _):
            """
            Updating the threshold
            """
            corruption_index = self._corruption_index
            threshold_index = int(np.floor(self.sframe2.val))
            if threshold_index != self._threshold_index:
                true_labels = self._experiment.uncorrupted_synthetic_test.labels
                predicted_labels = self._experiment.predicted_labels[corruption_index][threshold_index]
                self._axes[-1][0].clear()
                self._axes[-1][1].clear()
                self._experiment.synthetic_test[corruption_index].plot(true_labels, title='True Clustering',
                                                                       color_seed=self._color_seed, ax=self._axes[-1][0])
                self._experiment.synthetic_test[corruption_index].plot(predicted_labels, title='Predicted Clustering',
                                                                       color_seed=self._color_seed, ax=self._axes[-1][1])
                #self.pf1_dot.set_xdata(self._experiment.thresholds[threshold_index])
                #self.pf1_dot.set_ydata(self._experiment.metrics[corruption_index][threshold_index].pairwise_f1)
                #self.new_metrics_dot.set_xdata(self._experiment.thresholds[threshold_index])
                #self.new_metrics_dot.set_ydata(self._experiment.new_metrics[corruption_index][threshold_index].
                #                               net_expected_cost)
                for figure in self._figures:
                    figure.canvas.draw()
                self._threshold_index = threshold_index

    def __init__(self, number_entities, records_per_entity, train_database_size, validation_database_size,
                 train_class_balance, number_thresholds):
        ## Parameters ##
        self.corruption_multipliers = np.linspace(0, 0.025, 5)
        self.thresholds = np.linspace(0, 1, number_thresholds)
        ################
        uncorrupted_synthetic = SyntheticDatabase(number_entities, records_per_entity, number_features=2, sigma=0)
        self._uncorrupted_synthetic_train = uncorrupted_synthetic.sample_and_remove(train_database_size)
        self._uncorrupted_synthetic_validation = uncorrupted_synthetic.sample_and_remove(validation_database_size)
        self.uncorrupted_synthetic_test = uncorrupted_synthetic
        self._train_pair_seed = generate_pair_seed(self._uncorrupted_synthetic_train.database,
                                                   self._uncorrupted_synthetic_train.labels, train_class_balance)
        self._synthetic_train = list()
        self.synthetic_validation = list()
        self.synthetic_test = list()
        self.corruption_train = np.random.normal(loc=0.0, scale=1.0,
                                                 size=[train_database_size,
                                                 uncorrupted_synthetic.database.feature_descriptor.number])
        self.corruption_validation = np.random.normal(loc=0.0, scale=1.0,
                                                      size=[validation_database_size,
                                                      uncorrupted_synthetic.database.feature_descriptor.number])
        self.corruption_test = np.random.normal(loc=0.0, scale=1.0,
                                                size=[len(self.uncorrupted_synthetic_test.database.records),
                                                uncorrupted_synthetic.database.feature_descriptor.number])
        for multiplier in self.corruption_multipliers:
            new_train = deepcopy(self._uncorrupted_synthetic_train)
            new_validation = deepcopy(self._uncorrupted_synthetic_validation)
            new_test = deepcopy(self.uncorrupted_synthetic_test)
            new_train.corrupt(multiplier*self.corruption_train)
            new_validation.corrupt(multiplier*self.corruption_validation)
            new_test.corrupt(multiplier*self.corruption_test)
            self._synthetic_train.append(new_train)
            self.synthetic_test.append(new_test)
        self.predicted_labels, self.metrics, self.er, self.new_metrics = self.run()

    def run(self):
        """
        Runs ER for all corruption levels and all thresholds
        :return predicted_labels: List of lists of predicted labels.
                                  predicted_labels[corruption_index][threshold_index] = dict [identifier, cluster label]
        :return metrics: List of lists of metric objects.
                         metrics[corruption_index][threshold_index] = Metrics object
        :return er_objects: List of EntityResolution objects.
                            er_objects[corruption_index][threshold_index] = EntityResolution
        :return new_metrics_objects: List of NewMetrics objects.
                                    new_metrics_objects[corruption_index][threshold_index] = NewMetrics
        """
        predicted_labels = list()
        metrics = list()
        er_objects = list()
        new_metrics_objects = list()
        for synthetic_train, synthetic_test in izip(self._synthetic_train, self.synthetic_test):
            er = EntityResolution()
            weak_match_function = er.train(synthetic_train.database, synthetic_train.labels, self._train_pair_seed)
            print 'Testing pairwise match function precision and recall on validation database'
            roc = weak_match_function.test(synthetic_test.database, synthetic_test.labels, 0.5)
            class_balance_test = get_pairwise_class_balance(synthetic_test.labels)
            #roc.make_plot()
            metrics_sublist = list()
            labels_sublist = list()
            er_sublist = list()
            new_metrics_sublist = list()
            for threshold in self.thresholds:
                labels_pred = er.run(synthetic_test.database, weak_match_function, threshold, single_block=True,
                                     match_type='weak', max_block_size=np.Inf, cores=1)
                er_deepcopy = deepcopy(er)
                er_sublist.append(er_deepcopy)
                metrics_sublist.append(Metrics(synthetic_test.labels, labels_pred))
                new_metrics_sublist.append(NewMetrics(synthetic_test.database, er_deepcopy, class_balance_test))
                labels_sublist.append(labels_pred)
            metrics.append(metrics_sublist)
            new_metrics_objects.append(new_metrics_sublist)
            predicted_labels.append(labels_sublist)
            er_objects.append(er_sublist)
        return predicted_labels, metrics, er_objects, new_metrics_objects

    # def plot_metrics(self):
    #     """
    #     Makes precision/recall plots
    #     """
    #     pairwise_precision_array = np.empty((len(self.metrics), len(self.corruption_multipliers)))
    #     pairwise_recall_array = np.empty((len(self.metrics), len(self.corruption_multipliers)))
    #     pairwise_f1_array = np.empty((len(self.metrics), len(self.corruption_multipliers)))
    #     for threshold_index, metrics in enumerate(self.metrics):  # metrics at set threshold
    #         for corruption_index, metric in enumerate(metrics):  # metrics at set corruption
    #             pairwise_precision_array[threshold_index, corruption_index] = metric.pairwise_precision
    #             pairwise_recall_array[threshold_index, corruption_index] = metric.pairwise_recall
    #             pairwise_f1_array[threshold_index, corruption_index] = metric.pairwise_f1
    #
    #     ## Precision vs. Recall
    #     plt.plot(pairwise_recall_array, pairwise_precision_array)
    #     plt.title('Pairwise Precision Recall')
    #     plt.xlabel('Recall')
    #     plt.ylabel('Precision')
    #     plt.legend(self.corruption_multipliers.astype(str), title='Corruption')
    #     plt.show()
    #
    #     ## Precision v. Threshold
    #     plt.plot(self.thresholds, pairwise_precision_array)
    #     plt.title('Pairwise Precision')
    #     plt.xlabel('Threshold')
    #     plt.ylabel('Precision')
    #     plt.legend(self.corruption_multipliers.astype(str), title='Corruption')
    #     plt.show()
    #
    #     ## Recall v. Threshold
    #     plt.plot(self.thresholds, pairwise_recall_array)
    #     plt.title('Pairwise Recall')
    #     plt.xlabel('Threshold')
    #     plt.ylabel('Recall')
    #     plt.legend(self.corruption_multipliers.astype(str), title='Corruption')
    #     plt.show()
    #
    #     ## F1 v Threshold
    #     plt.plot(self.thresholds, pairwise_f1_array)
    #     plt.title('Pairwise F1')
    #     plt.xlabel('Threshold')
    #     plt.ylabel('F1')
    #     plt.legend(self.corruption_multipliers.astype(str), title='Corruption')
    #     plt.show()
    #
    #     print 'Threshold (rows) vs. Corruption Level (Columns)'
    #     print 'Pairwise Precision'
    #     np.set_printoptions(precision=5, suppress=True)  # no scientific notation
    #     print pairwise_precision_array
    #     print 'Pairwise Recall'
    #     print pairwise_recall_array
    #     print 'Pairwise F1'
    #     print pairwise_f1_array


class Experiment(object):
    """
    An experiment on a single synthetic or real database, with varying cutoff thresholds
    """
    class ResultsPlot(object):
        """
        Plot of the metrics at varying thresholds
        """
        def __init__(self, experiment):
            """
            :param experiment: Experiment parent object
            """
            print 'Plotting experimental results...'
            self._experiment = experiment

            self._threshold_index = 0

            # Plot the metrics
            self._figures = list()
            self._axes = list()

            ##############
            # ER Precision/Recall Lower Bound Debugging
            fig = plt.figure()
            self._figures.append(fig)
            ax = fig.add_subplot(111)
            #self._axes.append(ax)
            TP_FP_match = list()  # TP_match + FP_match
            TP_FP_swoosh = list()  # TP_swoosh + FP_swoosh
            for threshold_index, threshold in enumerate(experiment.thresholds):
                TP_FP_match.append(experiment.new_metrics[threshold_index].TP_FP_match)
                TP_FP_swoosh.append(experiment.new_metrics[threshold_index].TP_FP_swoosh)
            self.TP_FP_match, = ax.plot(experiment.thresholds, TP_FP_match, label='TP + FP, match', linewidth=2, color='g')
            self.TP_FP_swoosh, = ax.plot(experiment.thresholds, TP_FP_swoosh, label='TP + FP, swoosh', linewidth=2, color='r', linestyle='--')
            plt.legend(loc='upper left')
            ax.set_xlabel('Threshold')
            ax.set_ylabel('Count')
            ax.set_title('Lower Bound Debugging')


            # Match function precision recall curve
            fig = plt.figure()
            self._figures.append(fig)
            ax = fig.add_subplot(111)
            self._axes.append(ax)
            match_thresholds = experiment.er[self._threshold_index]._match_function.roc.prob
            match_precision = experiment.er[self._threshold_index]._match_function.roc.precision  # threshold index should be arbitrary
            match_recall = experiment.er[self._threshold_index]._match_function.roc.recall  # threshold index should be arbitrary
            match_f1 = experiment.er[self._threshold_index]._match_function.roc.f1  # threshold index should be arbitrary
            self.match_precision, = ax.plot(match_thresholds, match_precision, label='Precision', linewidth=2, color='#4477AA')  # blue
            self.match_recall, = ax.plot(match_thresholds, match_recall, label='Recall', linewidth=2, color='#CC6677')  # Magenta
            self.match_f1, = ax.plot(match_thresholds, match_f1, label='F1', linewidth=2, color='#DDCC77')  # Tan
            plt.legend(loc='upper left')
            ax.set_xlabel('Threshold')
            ax.set_ylabel('Score')
            ax.set_title('Match Function Performance')
            ax.set_xlim([0, 1.0])
            ax.set_ylim([0, 1.0])

            # Pairwise F1
            fig = plt.figure()
            self._figures.append(fig)
            ax = fig.add_subplot(111)
            #ax.grid(linestyle='--')
            self._axes.append([ax])
            pairwise_f1 = list()
            pairwise_f1_lower_bound = list()
            pairwise_precision = list()
            pairwise_precision_lower_bound = list()
            pairwise_recall = list()
            pairwise_recall_lower_bound = list()
            for threshold_index, threshold in enumerate(experiment.thresholds):
                pairwise_f1.append(experiment.metrics[threshold_index].pairwise_f1)
                pairwise_precision.append(experiment.metrics[threshold_index].pairwise_precision)
                pairwise_recall.append(experiment.metrics[threshold_index].pairwise_recall)
                pairwise_precision_lower_bound.append(experiment.new_metrics[threshold_index].precision_lower_bound)
                pairwise_recall_lower_bound.append(experiment.new_metrics[threshold_index].recall_lower_bound)
                pairwise_f1_lower_bound.append(experiment.new_metrics[threshold_index].f1_lower_bound)
            self.pf1, = ax.plot(experiment.thresholds, pairwise_f1, label='F1', linewidth=2, color='#DDCC77', linestyle='--')
            self.pp, = ax.plot(experiment.thresholds, pairwise_precision, label='Precision', linewidth=2, color='#4477AA', linestyle='--')
            self.pr, = ax.plot(experiment.thresholds, pairwise_recall, label='Recall', linewidth=2, color='#CC6677', linestyle='--')
            #self.pf1_dot, = ax.plot(experiment.thresholds[self._threshold_index], pairwise_f1[self._threshold_index],
            #                        'bo', markersize=10, label='Operating Point')
            self.pf1_lower, = ax.plot(experiment.thresholds, pairwise_f1_lower_bound, label='F1 Lower Bound', linewidth=2, color='#DDCC77')
            self.pp_lower, = ax.plot(experiment.thresholds, pairwise_precision_lower_bound, label='Precision Lower Bound', linewidth=2, color='#4477AA')
            self.pr_lower, = ax.plot(experiment.thresholds, pairwise_recall_lower_bound, label='Recall Lower Bound', linewidth=2, color='#CC6677')
            plt.legend(loc='upper left')
            self._axes[1][0].set_xlabel('Threshold')
            self._axes[1][0].set_ylabel('Pairwise Metric')
            self._axes[1][0].set_title('Pairwise Metrics')
            self._axes[1][0].set_ylim([0, 1.0])
            #################

            # Pairwise
            # self._figures.append(plt.figure())
            # ax = self._figures[0].add_subplot(111)
            # ax.grid(linestyle='--')
            # self._axes.append([ax])
            # pairwise_f1 = list()
            # pairwise_precision = list()
            # pairwise_recall = list()
            # for threshold_index, threshold in enumerate(experiment.thresholds):
            #     pairwise_f1.append(experiment.metrics[threshold_index].pairwise_f1)
            #     pairwise_precision.append(experiment.metrics[threshold_index].pairwise_precision)
            #     pairwise_recall.append(experiment.metrics[threshold_index].pairwise_recall)
            # ax.plot(experiment.thresholds, pairwise_f1, label='Pairwise F1')
            # ax.plot(experiment.thresholds, pairwise_precision, label='Pairwise Precision')
            # ax.plot(experiment.thresholds, pairwise_recall, label='Pairwise Recall')
            # plt.legend(loc='upper left')
            # self._axes[0][0].set_xlabel('Threshold')
            # self._axes[0][0].set_ylabel('Score')
            # self._axes[0][0].set_title('Pairwise Metrics')
            # self._axes[0][0].set_ylim([0, 1.0])
            #
            # # Number of entities
            # self._figures.append(plt.figure())
            # ax = self._figures[2].add_subplot(111)
            # ax.grid(linestyle='--')
            # self._axes.append([ax])
            # number_entities = list()
            # for threshold_index, threshold in enumerate(experiment.thresholds):
            #     number_entities.append(experiment.metrics[threshold_index].number_entities)
            # ax.plot(experiment.thresholds, number_entities)
            # self._axes[2][0].set_xlabel('Threshold')
            # self._axes[2][0].set_ylabel('Number of Entities')
            # self._axes[2][0].set_title('Number of Resolved Entities')
            #
            # # Closest cluster metrics
            # self._figures.append(plt.figure())
            # ax = self._figures[3].add_subplot(111)
            # ax.grid(linestyle='--')
            # self._axes.append([ax])
            # closest_cluster_f1 = list()
            # closest_cluster_precision = list()
            # closest_cluster_recall = list()
            # for threshold_index, threshold in enumerate(experiment.thresholds):
            #     closest_cluster_f1.append(experiment.metrics[threshold_index].closest_cluster_f1)
            #     closest_cluster_precision.append(experiment.metrics[threshold_index].closest_cluster_precision)
            #     closest_cluster_recall.append(experiment.metrics[threshold_index].closest_cluster_recall)
            # ax.plot(experiment.thresholds, closest_cluster_f1, label='Closest Cluster F1')
            # ax.plot(experiment.thresholds, closest_cluster_precision, label='Closest Cluster Precision')
            # ax.plot(experiment.thresholds, closest_cluster_recall, label='Closest Cluster Recall')
            # plt.legend(loc='upper left')
            # self._axes[3][0].set_xlabel('Threshold')
            # self._axes[3][0].set_ylabel('Score')
            # self._axes[3][0].set_title('Closest Cluster Metrics')
            # self._axes[3][0].set_ylim([0, 1.0])
            plt.show()

    def __init__(self, database_train, database_validation, database_test, labels_train, labels_validation, labels_test,
                 train_class_balance, thresholds):
        """
        Performs entity resolution on a database at varying thresholds
        :param database_train: Database object for training match function
        :param database_validation: Database object for estimating match precision/recall performance
        :param database_test: Database object for testing entity resolution
        :param labels_train: A dictionary of the true labels [record id, label]
        :param labels_validation: A dictionary of the true labels [record id, label]
        :param labels_test: A dictionary of the true labels [record id, label]
        :param train_class_balance: Float [0, 1.0]. Train with this percent of positive samples
        :param thresholds: List of thresholds to run ER at
        """
        self._database_train = database_train
        self._database_validation = database_validation
        self._database_test = database_test
        self._labels_train = labels_train
        self._labels_validation = labels_validation
        self._labels_test = labels_test
        self._train_class_balance = train_class_balance
        self.thresholds = thresholds
        print 'Generating pairwise seed for training database'
        self._train_pair_seed = generate_pair_seed(self._database_train, self._labels_train, train_class_balance)
        self._predicted_labels, self.metrics, self.er, self.new_metrics = self.run()

    def run(self):
        """
        Runs ER at all thresholds
        :return predicted_labels: List of lists of predicted labels.
                                  predicted_labels[threshold_index] = dict [identifier, cluster label]
        :return metrics: List of lists of metric objects.
                         metrics[threshold_index] = Metrics object
        :return er_objects: List of EntityResolution objects.
                            er_objects[threshold_index] = EntityResolution
        :return new_metrics_objects: List of NewMetrics objects.
                                    new_metrics_objects[threshold_index] = NewMetrics
        """
        er = EntityResolution()
        weak_match_function = er.train(self._database_train, self._labels_train, self._train_pair_seed)
        print 'Testing pairwise match function on test database'
        ROC = weak_match_function.test(self._database_validation, self._labels_validation, 0.5)
        #ROC.make_plot()
        metrics_list = list()
        labels_list = list()
        er_list = list()
        new_metrics_list = list()
        class_balance_test = get_pairwise_class_balance(self._labels_test)
        for threshold in self.thresholds:
            print 'Running entity resolution at threshold =', threshold
            labels_pred = er.run(self._database_test, weak_match_function, threshold, single_block=True,
                                 match_type='weak', max_block_size=np.Inf, cores=1)
            er_deepcopy = deepcopy(er)
            er_list.append(er_deepcopy)
            metrics_list.append(Metrics(self._labels_test, labels_pred))
            new_metrics_list.append(NewMetrics(self._database_test, er_deepcopy, class_balance_test))
            labels_list.append(labels_pred)
        return labels_list, metrics_list, er_list, new_metrics_list


def get_pairwise_class_balance(labels):
    """
    Returns the percent of positive pairs out of all the pairs in database.
    Eventually this should be automated with density estimates, using a train database, train labels, and test database
    :param labels: Corresponding labels for the database object. Dict of [record id, label]
    :return class_balance: Percent of positive pairs in database, [0, 1.0]
    """
    print 'Calculating class balance'
    number_records = len(labels)
    total_number_pairs = number_records*(number_records-1)/2
    print '     Total number of pairs:', total_number_pairs
    clusters = _cluster(labels)
    total_number_positive_pairs = 0.0
    for cluster in clusters:
        number_cluster_pairs = len(cluster)*(len(cluster)-1)/2
        total_number_positive_pairs += number_cluster_pairs
    print '     Number of positive pairs:', total_number_positive_pairs
    class_balance = total_number_positive_pairs/total_number_pairs
    print '     Class balance:', class_balance
    return class_balance


def main():
    #### Real Experiment ####
    number_thresholds = 15
    dataset_name = 'restaurant'  # synthetic, restaurant, abt-buy

    if dataset_name == 'synthetic':
        number_entities = 10
        records_per_entity = 30
        train_database_size = 100
        train_class_balance = 0.5
        validation_database_size = 100
        synthetic_experiment = SyntheticExperiment(number_entities, records_per_entity,
                                                   train_database_size, validation_database_size,
                                                   train_class_balance, number_thresholds)
        synthetic_plot = synthetic_experiment.ResultsPlot(synthetic_experiment)
        pickle.dump(synthetic_experiment, open('synthetic_experiment.p', 'wb'))
    else:
        if dataset_name == 'restaurant':  # 864 records, 112 matches
            features_path = '../data/restaurant/merged.csv'
            labels_path = '../data/restaurant/labels.csv'
            train_database_size = 300
            train_class_balance = .4
            validation_database_size = 200
        elif dataset_name == 'abt-buy':  # ~4900 records, 1300 matches
            features_path = '../data/Abt-Buy/merged.csv'
            labels_path = '../data/Abt-Buy/labels.csv'
            train_database_size = 1500
            number_train_pairs = 500
            number_test_pairs = 200
        else:
            raise Exception('Invalid dataset name')

        thresholds = np.linspace(0, 1, number_thresholds)
        database = Database(annotation_path=features_path)
        database_train = database.sample_and_remove(train_database_size)
        database_validation = database.sample_and_remove(validation_database_size)
        database_test = database
        labels = np.loadtxt(open(labels_path, 'rb'))
        labels_train = dict()
        labels_validation = dict()
        labels_test = dict()
        for identifier, label in enumerate(labels):
            if identifier in database_train.records:
                labels_train[identifier] = label
            elif identifier in database_validation.records:
                labels_validation[identifier] = label
            elif identifier in database_test.records:
                labels_test[identifier] = label
            else:
                raise Exception('Record identifier ' + str(identifier) + ' not in either database')
        experiment = Experiment(database_train, database_validation, database_test,
                                labels_train, labels_validation, labels_test,
                                train_class_balance, thresholds)
        #print 'Saving results'
        #pickle.dump(experiment, open('experiment.p', 'wb'))
        plot = experiment.ResultsPlot(experiment)
    print 'Finished'

if __name__ == '__main__':
    cProfile.run('main()')
