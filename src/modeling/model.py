# model.py

import os
import sys
import itertools
import pickle
from os.path import isfile

import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx
import numpy as np
import seaborn as sns
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots

import plotly.io as pio

pio.renderers.default = "browser"

import math


from jmapper import JMapper
from jbottle import JBottle

from model_helper import (
    config_plot_data,
    custom_color_scale,
    get_minimal_std,
    mapper_plot_outfile,
    reorder_colors,
    get_subplot_specs,
    _define_zscore_df,
)
from persim import plot_diagrams


class Model():
    """A clustering model for point cloud data
    based on the Mapper Algorithm.

    This class interprets the graph representation of a JMapper
    as a clustering:
    Connected Components of the graph are the clusters which we call
    "Policy self.index_dict" for our project. We provide functionality
    for analyzing nodes (or subself.index_dict),
    as well as the policy self.index_dict themselves.

    Most notably, we provide functionality for understanding the structural
    equivalency classes of an arbitrary number of different models. Different
    meaning the models are generated from different hyperparameters, but it
    may be that the graphs they generate have very similar structure. We
    analyze these structural equivalence classes using the functioanlity
    in JMapper for computing curvature filtrations on graphs.

    We also provide functionality for visualizing various attributes
    of our graph models.
    """

    def __init__(self, jmapper, jbottle):
        """Constructor for Model class.
        Parameters
        -----------

        jmapper:str
          Path to a Jmapper object 
        """
        
        try:
            with open(jmapper, 'rb') as f:
                reference = pickle.load(f)
            self._jmapper = reference['mapper']
            self._hyper_parameters = reference['hyperparameters']
        except: 
            print("There was an error opening your Jmapper Object")
        

        self._jbottle = JBottle(self._jmapper.tupper, self._jmapper.jgraph.connected_components)
        
        # Graph Node Attributes
        self._node_ids = None
        self._node_description = None

        # TODO: Move this to JBOTTLE 

        # As a rule, if it has to do with pure data analysis 
        # then it belongs in JBottle 
        # data analysis utility functions on pd.DataFrames will be written into 
        # data_utils.py 

        # REMOVE! 
        self._cluster_ids = None
        self._cluster_sizes = None
        self._unclustered_items = None
        self._zscores = None
        self._items_dict = None

        # Keep! 
        self._cluster_descriptions = None
        self._cluster_positions = None


    @property
    def hyper_parameters(self):
        """Return the hyperparameters used to fit this model."""
        return self._hyper_parameters


    @property
    def node_description(self):
        """Return the node descriptions according to the graph clustering."""
        if self._node_description is None:
            self.compute_node_descriptions()
        return self._node_description
    
    # TODO: RENAME 
    @property
    def cluster_descriptions(self):
        """Return the policy group descriptions according
        to the graph clustering."""
        if self._cluster_descriptions is None:
            self.compute_cluster_descriptions()
        return self._cluster_descriptions
    

###################################################################################################

# TODO: Get Rid of the Below

###################################################################################################
 
    @property
    def node_ids(self):
        """Return the node labels according to the graph clustering."""
        if self._node_ids is None:
            self.label_item_by_node()
        return self._node_ids
    
    # TODO: Move This to JBottle
    @property
    def cluster_ids(self):
        """Return the policy group labels according to the graph clustering."""
        if self._cluster_ids is None:
            self.label_item_by_cluster()
        return self._cluster_ids

    @property
    def cluster_sizes(self):
        """Return the policy group sizes according to the graph clustering."""
        if self._cluster_sizes is None:
            self.label_item_by_cluster()
        return self._cluster_sizes

    @property
    def unclustered_items(self):
        """Return the items left out of the graph clustering."""
        if self._unclustered_items is None:
            self.label_item_by_node()
        return self._unclustered_items
    
    @property
    def items_dict(self):
        if self._items_dict is None:
            self.label_item_by_cluster()
        return self._items_dict

    @property
    def zscores(self):
        if self._zscores is None:
            self._zscores = (
                _define_zscore_df(self).groupby(["cluster_IDs"]).mean().reset_index()
            )
        return self._zscores

    def group_identifiers(self, zscore_threshold=1, std_threshold=1):

        pg_identifiers = {
            key: [] for key in range(-1, int(self.zscores["cluster_IDs"].max()) + 1)
        }
        for column in self.zscores.columns:
            counter = -1
            for value in self.zscores[column]:
                if column != "cluster_IDs":
                    if abs(value) >= zscore_threshold:
                        test = _define_zscore_df(self)[
                            _define_zscore_df(self)["cluster_IDs"] == counter
                        ]
                        if (
                            abs(test[column].std() / test[column].mean())
                            <= std_threshold
                        ):
                            pg_identifiers[counter].append(column)
                counter += 1
        self._group_identifiers = pg_identifiers
        return self._group_identifiers

    def label_item_by_node(self):
        """Label each item in the data set according to its corresponding
        node in the graph.

        This function loops through each of the connected components in
        the graph and labels each item with the component ID
        of the corresponding node.

        Returns
        -------
        self._cluster_ids : np.ndarray, shape (N,)
            Array with policy group (cluster) ID for each item in the data.
        """
        N = len(self.tupper.clean)
        labels = dict()
        nodes = self.complex["nodes"]
        unclustered_items = []
        for idx in range(N):
            place_holder = []
            for node_id in nodes.keys():
                if idx in nodes[node_id]:
                    place_holder.append(node_id)

            if len(place_holder) == 0:
                place_holder = -1
                unclustered_items.append(idx)
            labels[idx] = place_holder

        self._node_ids = labels
        self._unclustered_items = unclustered_items
        return self._node_ids

    def label_item_by_cluster(self):
        """Label each item in the data set according to its corresponding
        policy group, i.e. connected component in the graph.

        Returns
        -------
        self._node_description : dict
            Dictionary with node ID as key and a string with the node
            description as value.
        """
        assert (
            len(self.complex) > 0
        ), "You must first generate a Simplicial Complex with `fit()` before you perform clustering."

        self._cluster_sizes = {}
        self._items_dict = {}

        labels = -np.ones(len(self.tupper.clean))
        components = self.mapper.components
        for component in components.keys():
            cluster_id = components[component]
            nodes = component.nodes()

            elements = []
            for node in nodes:
                elements.append(self.complex["nodes"][node])

            indices = set(itertools.chain(*elements))
            self._items_dict[cluster_id] = list(indices)
            size = len(indices)
            labels[list(indices)] = cluster_id
            self._cluster_sizes[cluster_id] = size

        self._cluster_ids = labels
        self._cluster_sizes[-1] = len(self.unclustered_items)
        self.items_dict[-1] = self.unclustered_items

    def get_items_in_multiple_groups(self):
        """
        Get a dictionary of overlapping values that appear in more than one group.

        Returns
        -------
            overlapping_values: A dictionary where keys are the overlapping values and values are lists
                of groups (keys) in which the value appears.
        """
        overlapping_values = {}

        # Count the occurrences of each value across the self.index_dict
        value_counts = {}
        for values in self.items_dict.values():
            for value in values:
                value_counts[value] = value_counts.get(value, 0) + 1

        # Filter the overlapping values that appear in more than one group
        for value, count in value_counts.items():
            if count > 1:
                overlapping_values[value] = [key for key, values in self.items_dict.items() if value in values]

        return overlapping_values

    

###################################################################################################

# TODO: Get Rid of the above 

###################################################################################################


    def compute_node_descriptions(self):
        """
        Compute a simple description of each node in the graph.

        This function labels each node based on the column in
        the dataframe that admits the smallest (normalized)
        standard deviation amongst items in the node.

        As a note, we only consider columns that are:
            1) continuous in the raw data
            2) used to fit JMapper, i.e. appear in clean data

        Returns
        -------
        self._node_description : dict
            Dictionary with node ID as key and a string with the node
            description as value.
        """
        nodes = self.complex["nodes"]
        cols = np.intersect1d(
            self.tupper.raw.select_dtypes(include=["number"]).columns,
            self.tupper.clean.columns,
        )
        self._node_description = {}
        for node in nodes.keys():
            mask = nodes[node]
            label = get_minimal_std(
                df=self.tupper.clean,
                mask=mask,
                density_cols=cols,
            )
            size = len(mask)
            self._node_description[node] = {"label": label, "size": size}

    def compute_cluster_descriptions(self):
        """
        Compute a simple description of each cluster (policy group).

        This function creates a density description based on each of
        the node lables in the policy group.

        Returns
        -------
        self._cluster_descriptions : dict
            Dictionary with cluster ID as key and a dictionary with the
            labeled density descriptions as values.
        """
        self._cluster_descriptions = {}
        components = self.mapper.components
        # View cluster as networkX graph
        for G in components.keys():
            cluster_id = components[G]
            nodes = G.nodes()
            holder = {}
            N = 0
            for node in nodes:
                label = self.node_description[node]["label"]
                size = self.node_description[node]["size"]

                N += size
                # If multiple nodes have same identifying column
                if label in holder.keys():
                    size += holder[label]
                holder[label] = size
            density = {label: np.round(size / N, 2) for label, size in holder.items()}
            self._cluster_descriptions[cluster_id] = {
                "density": density,
                "size": self.cluster_sizes[cluster_id],
            }

        # Desnity of Unclustered Items
        cols = np.intersect1d(
            self.tupper.raw.select_dtypes(include=["number"]).columns,
            self.tupper.clean.columns,
        )
        unclustered_label = get_minimal_std(
            df=self.tupper.clean,
            mask=self.unclustered_items,
            density_cols=cols,
        )
        self._cluster_descriptions[-1] = {
            "density": {unclustered_label: 1.0},
            "size": self.cluster_sizes[-1],
        }
###################################################################################################

# TODO: Git outta here (below)

###################################################################################################
    def _get_node_df(self, node: str):
        """helper function for get_node_dfs that creates a data frame containing each plant in a specified node"""
        df = self.tupper.raw
        return df.loc[list(self.mapper.complex["nodes"][node])]

    def get_node_dfs(self, cc: int):

        """
        Generate a DataFrame for each node within a policy group.
        Note: unclustered items are given their own DataFrame.

        Inputs
        -------
        cc : int
            An integer corresponding to the policy group # (cluster #) you wish to examine nodes within.

        Returns
        -------
        subframes: dict
            A dictionary where each key is a node ID
            and the corresponding value is a DataFrame containing
            the items in that node.
        """

        node_dict = {}
        graph, key = list(self.mapper.components.items())[cc]
        graph.nodes()
        nodes = list(graph.nodes())

        for node in nodes:
            node_dict[node] = self._get_node_df(node)

        return node_dict

    def _get_node_df(self, node: str):
        """helper function for get_node_dfs that creates a data frame containing each plant in a specified node"""
        df = self.tupper.raw
        return df.loc[list(self.mapper.complex["nodes"][node])]

    def get_node_dfs(self, cc: int):

        """
        Generate a DataFrame for each node within a policy group.
        Note: unclustered items are given their own DataFrame.

        Inputs
        -------
        cc : int
            An integer corresponding to the policy group # (cluster #) you wish to examine nodes within.

        Returns
        -------
        subframes: dict
            A dictionary where each key is a node ID
            and the corresponding value is a DataFrame containing
            the items in that node.
        """

        node_dict = {}
        graph, key = list(self.mapper.components.items())[cc]
        graph.nodes()
        nodes = list(graph.nodes())

        for node in nodes:
            node_dict[node] = self._get_node_df(node)

        return node_dict

    def get_cluster_dfs(self):
        """
        Generate a DataFrame for each policy group.
        Note: unclustered items are given their own DataFrame.

        Returns
        -------
        subframes: dict
            A dictionary where each key is a policy group (cluster) ID
            and the corresponding value is a DataFrame containing
            the items in that policy group.
        """

        group_dataframes = {}

        for group_label, indexes in self.items_dict.items():
            df = self.tupper.clean.copy()
            df.loc[indexes, 'group'] = group_label
            
            sub_frame = df[df["group"] == group_label]
            # Merge with Raw
            raw_subframe = pd.merge(
                sub_frame["group"],
                self.tupper.raw,
                right_index=True,
                left_index=True,
            )
            
            group_dataframes[f"group_{group_label}"] = raw_subframe 

        return group_dataframes
    

    ###################################################################################################

# TODO: Git outta here (above)

###################################################################################################

    def target_matching(
        self,
        target: pd.DataFrame,
        remove_unclustered: bool = True,
        col_filter: list = None,
    ):

        self.index_dict = self.get_cluster_dfs()
        # Remove Unclustered? -> at least for demo
        if remove_unclustered and len(self.unclustered_items) > 0:
            self.index_dict.pop("group_-1")

        target_cols = (
            target.select_dtypes(include=np.number).dropna(axis=1).columns
        )
        if col_filter:
            raw_cols = col_filter
        else:
            raw_cols = self.tupper.raw.select_dtypes(include=np.number).columns

        def error(x, mu):
            return abs((x - mu) / mu)

        scores = {}
        for group in self.index_dict:
            group_data = self.index_dict[group]
            score = 0
            for col in target_cols:
                if col in raw_cols:
                    x = target[col][0]
                    mu = group_data[col].mean()
                    score += error(x, mu)
            scores[group] = score

        min_index = min(scores, key=scores.get)
        return scores, min_index
    

    # Wut 
    def fib(self, i, g, colorscale):
        return colorscale[i]

    def visualize_model(self, k=None, seed=6):
        """
        Visualize the clustering as a network. This function plots
        the JMapper's graph in a matplotlib figure, coloring the nodes
        by their respective policy group.

        Parameters
        -------
        k : float, default is None
            Optimal distance between nodes. If None the distance is set to
            1/sqrt(n) where n is the number of nodes. Increase this value to
            move nodes farther apart.

        """
        # Config Pyplot
        fig = plt.figure(figsize=(14, 8))
        ax = fig.add_subplot()
        color_scale = np.array(custom_color_scale()).T[1]
        # Get Node Coords
        pos = nx.spring_layout(self.mapper.graph, k=k, seed=seed)

        # Plot and color components
        components, labels = zip(*self.mapper.components.items())
        for i, g in enumerate(components):
            nx.draw_networkx(
                g,
                pos=pos,
                #node_color=color_scale[i],
                node_color = self.fib(i, g, color_scale),
                node_size=100,
                font_size=6,
                with_labels=False,
                ax=ax,
                label=f"Group {labels[i]}",
                edgelist=[],
            )
            nx.draw_networkx_edges(
                g,
                pos=pos,
                width=2,
                ax=ax,
                label=None,
                alpha=0.6,
            )
        ax.legend(loc="best", prop={"size": 8})
        plt.axis("off")
        self._cluster_positions = pos
        return plt

    def visualize_component(self, component, cluster_labels=True):
        if self._cluster_positions is None:
            return "Ensure you have run .visualize_model() before attempting to visualize a component"

        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot()

        color_scale = np.array(custom_color_scale()).T[1]
        components, labels = zip(*self.mapper.components.items())
        for i, g in enumerate(components):
            if i == component:
                nx.draw_networkx(
                    g,
                    pos=self._cluster_positions,
                    node_color=color_scale[i],
                    node_size=100,
                    font_size=10,
                    with_labels=cluster_labels,
                    ax=ax,
                    label=f"Group {labels[i]}",
                    # font_color = color_scale[i],
                    edgelist=[],
                )
                nx.draw_networkx_edges(
                    g,
                    pos=self._cluster_positions,
                    width=2,
                    ax=ax,
                    label=None,
                    alpha=0.6,
                )
        ax.legend(loc="best", prop={"size": 8})
        plt.axis("off")
        # return fig

    def visualize_projection(self, show_color=True, show_axis=False):
        """
        Visualize the clustering on the projection point cloud.
        This function plots the projection used to fit JMapper
        and colors points according to their cluster.
        """
        color_scale = np.array(custom_color_scale()).T[1]

        projection, parameters = (
            self.tupper.projection,
            self.tupper.get_projection_parameters(),
        )
        if show_color:
            fig = go.Figure()
            for g in np.unique(self.cluster_ids):
                label = f"Policy Group {int(g)}"
                if g == -1:
                    label = "Unclustered Items"
                mask = np.where(self.cluster_ids == g, True, False)
                cluster = projection[mask]
                fig.add_trace(
                    go.Scatter(
                        x=cluster.T[0],
                        y=cluster.T[1],
                        mode="markers",
                        marker=dict(color=color_scale[int(g)]),
                        name=label,
                    )
                )
        else:
            fig = go.Figure()
            for g in np.unique(self.cluster_ids):
                label = f"Policy Group {int(g)}"
                if g == -1:
                    label = "Unclustered Items"
                mask = np.where(self.cluster_ids == g, True, False)
                cluster = projection[mask]
                fig.add_trace(
                    go.Scatter(
                        x=cluster.T[0],
                        y=cluster.T[1],
                        mode="markers",
                        marker=dict(color="grey"),
                        showlegend=False,
                    )
                )
        if show_axis:
            fig.update_layout(
                title=f"UMAP: {parameters}",
                legend=dict(
                    title="",
                    bordercolor="black",
                    borderwidth=1,
                ),
                width=800,
                height=600,
            )
        else:
            fig.update_layout(
                # title=f"UMAP: {parameters}",
                width=800,
                height=600,
                showlegend=False,
                xaxis=dict(
                    tickcolor="white",
                    showticklabels=False,
                    showgrid=False,
                    zeroline=False,
                    showline=False,
                ),
                yaxis=dict(
                    tickcolor="white",
                    showticklabels=False,
                    showgrid=False,
                    zeroline=False,
                    showline=False,
                ),
            )

        fig.update_layout(template="simple_white")
        return fig

    def visualize_piecharts(self):
        # Define the color map based on the dictionary values
        colors = []

        for i in range(len(custom_color_scale()[:-3])):
            inst = custom_color_scale()[:-3]
            rgb_color = "rgb" + str(
                tuple(int(inst[i][1][j : j + 2], 16) for j in (2, 3, 5))
            )
            colors.append(rgb_color)

        colors = reorder_colors(colors)
        color_map = {
            key: colors[i % len(colors)]
            for i, key in enumerate(
                set.union(
                    *[
                        set(v["density"].keys())
                        for v in self.cluster_descriptions.values()
                    ]
                )
            )
        }        
        cluster_descriptions = self.cluster_descriptions
        if cluster_descriptions[-1]['size'] == 0:
            cluster_descriptions.pop(-1)

        num_rows = math.ceil(max(len(cluster_descriptions) / 3, 1))
        print(len(cluster_descriptions))
        specs = get_subplot_specs(len(cluster_descriptions))

        dict_2 = {i: f"Group {i}" for i in range(len(cluster_descriptions))}
        dict_2 = {-1: "Outliers", **dict_2}
        fig = make_subplots(
            rows=num_rows,
            cols=3,
            specs=specs,
            subplot_titles=[
                f"<b>{dict_2[key]}</b>: {cluster_descriptions[key]['size']} Members"
                for key in cluster_descriptions
            ],
            horizontal_spacing=0.1,
        )

        for i, key in enumerate(cluster_descriptions):
            density = cluster_descriptions[key]["density"]

            labels = list(density.keys())
            sizes = list(density.values())

            # labels_list = [labels.get(item, item) for item in labels]

            row = i // 3 + 1
            col = i % 3 + 1
            fig.add_trace(
                go.Pie(
                    labels=labels,
                    textinfo="percent",
                    values=sizes,
                    textposition="outside",
                    marker_colors=[color_map[l] for l in labels],
                    scalegroup=key,
                    hole=0.5,
                ),
                row=row,
                col=col,
            )

        fig.update_layout(
            template="plotly_white", showlegend=True, 
            #height=600, 
            height = num_rows * 300,
            width=800
        )

        fig.update_annotations(yshift=10)

        fig.update_traces(marker=dict(line=dict(color="white", width=3)))

        # TODO: Base this yshift on the number of descriptors 
        y_shift = -2 

        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=y_shift, xanchor="left", x=0)
        )

        config = {
        'toImageButtonOptions': {
            'format': 'svg', # one of png, svg, jpeg, webp
            'filename': 'custom_image',
            'scale':5 # Multiply title/legend/axis/canvas sizes by this factor
        }
        }

        # Show the subplot
        fig.show(config=config)

    def visualize_boxplots(self, cols=[], target=pd.DataFrame()):

        show_targets = False
        if len(target) == 1:
            numeric_cols = (
                target.select_dtypes(include=["number"]).dropna(axis=1).columns
            )
            target = target[numeric_cols]
            show_targets = True

        df = self.tupper.raw
        df["cluster_IDs"] = self.cluster_ids

        if len(cols) > 0:
            cols.append("cluster_IDs")
            df = df.loc[:, df.columns.isin(cols)]

        fig = make_subplots(
            rows=math.ceil(len(df.columns.drop("cluster_IDs")) / 3),
            cols=3,
            horizontal_spacing=0.1,
            subplot_titles=df.columns.drop("cluster_IDs"),
        )

        row = 1
        col = 1

        if -1.0 not in list(df.cluster_IDs.unique()):
            dict_2 = {i: str(i) for i in range(len(list(df.cluster_IDs.unique())))}
        else:
            dict_2 = {i: str(i) for i in range(len(list(df.cluster_IDs.unique()))-1)}
        dict_2 = {-1: "Outliers", **dict_2}

        for column in df.columns.drop("cluster_IDs"):
            for pg in list(dict_2.keys()):
                fig.add_trace(
                    go.Box(
                        y=self.get_cluster_dfs()[f"group_{pg}"][column],
                        name=dict_2[pg],
                        jitter=0.3,
                        showlegend=False,
                        whiskerwidth=0.6,
                        marker_size=3,
                        line_width=1,
                        boxmean=True,
                        #hovertext=df["companyName"],
                        marker=dict(color=custom_color_scale()[int(pg)][1]),
                    ),
                    row=row,
                    col=col,
                )

                if show_targets:
                    if column in target.columns:
                        fig.add_hline(
                            y=target[column].mean(),
                            line_width=1,
                            line_dash="solid",
                            line_color="red",
                            col=col,
                            row=row,
                            annotation_text="target",
                            annotation_font_color="red",
                            annotation_position="top left",
                        )

                try:
                    pd.to_numeric(df[column])
                    fig.add_hline(
                        y=df[column].mean(),
                        line_width=1,
                        line_dash="dash",
                        line_color="black",
                        col=col,
                        row=row,
                        annotation_text="mean",
                        annotation_font_color="gray",
                        annotation_position="top right",
                    )
                except ValueError:
                    """"""

            col += 1
            if col == 4:
                col = 1
                row += 1

        fig.update_layout(
            template="simple_white",
            height=(math.ceil(len(df.columns) / 3)) * 300,
            title_font_size=20,
        )

        config = {
            'toImageButtonOptions': {
                'format': 'svg', # one of png, svg, jpeg, webp
                'filename': 'custom_image',
                'height': 1200,
                'width': 1000,
                'scale':5 # Multiply title/legend/axis/canvas sizes by this factor
            }
        }

        fig.show(config = config)

    def visualize_curvature(self, bins="auto", kde=False):
        """Visualize th curvature of a graph graph as a histogram.

        Parameters
        ----------
        bins: str, default is "auto"
            Method for seaborn to assign bins in the histogram.
        kde: bool
            If true then draw a density plot.
        """

        ax = sns.histplot(
            self.mapper.curvature,
            discrete=True,
            stat="probability",
            kde=kde,
            bins=bins,
        )
        ax.set(xlabel="Ollivier Ricci Edge Curvatures")
        plt.show()

    def visualize_persistence_diagram(self):
        """Visualize persistence diagrams of a mapper graph
        using functionality from Persim."""
        assert len(self.mapper.diagram) > 0, "Persistence Diagram is empty."
        persim_diagrams = [
            np.asarray(self.mapper.diagram[0]._pairs),
            np.asarray(self.mapper.diagram[1]._pairs),
        ]
        return plot_diagrams(persim_diagrams, show=True)


    # Maybe its time we let the old ways die? 

    @DeprecationWarning
    def visualize_mapper(self):
        """
        Plot using the Keppler Mapper html functionality.

        NOTE: These visualizations are no longer maintained by KepplerMapper
        and we do not reccomend using them.
        """
        assert len(self.complex) > 0, "Model needs a `fitted` mapper."
        kepler = self.mapper.mapper
        path_html = mapper_plot_outfile(self.hyper_parameters)
        numeric_data, labels = config_plot_data(self.tupper)

        colorscale = custom_color_scale()
        # Use Kmapper Visualization
        kepler.visualize(
            self.mapper.complex,
            node_color_function=["mean", "median", "std", "min", "max"],
            color_values=numeric_data,
            color_function_name=labels,
            colorscale=colorscale,
            path_html=path_html,
        )

        print(f"Go to {path_html} for a visualization of your JMapper!")
