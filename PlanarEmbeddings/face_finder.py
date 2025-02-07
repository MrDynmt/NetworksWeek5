#Most code due to Lorenzo Najt
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from gerrychain import Graph

g = Graph.from_json("./County/dual_graphs/County08.json")
df = gpd.read_file("./County/County08.shp")
print(len(g.nodes),'nodes')
print(len(g.edges),'edges')
centroids = df.centroid
c_x = centroids.x
c_y = centroids.y
#shape = True

nlist = list(g.nodes())
n = len(nlist)


#pos = nx.kamada_kawai_layout(g)
#if shape:
pos = {node:(c_x[node],c_y[node]) for node in g.nodes}

for node in g.nodes():
    g.nodes[node]["pos"] = np.array(pos[node])


def compute_rotation_system(graph):
    #Graph nodes must have "pos"
    #The rotation system is  clockwise (0,2) -> (1,1) -> (0,0) around (0,1)
    for v in graph.nodes():
        graph.node[v]["pos"] = np.array(graph.node[v]["pos"])
    
    for v in graph.nodes():
        locations = []
        neighbor_list = list(graph.neighbors(v))
        for w in neighbor_list:
            locations.append(graph.node[w]["pos"] - graph.node[v]["pos"])
        angles = [float(np.arctan2(x[0], x[1])) for x in locations]
        neighbor_list.sort(key=dict(zip(neighbor_list, angles)).get)
        #sorted_neighbors = [x for _,x in sorted(zip(angles, neighbor_list))]
        rotation_system = {}
        for i in range(len(neighbor_list)):
            rotation_system[neighbor_list[i]] = neighbor_list[(i + 1) % len(neighbor_list)]
        graph.node[v]["rotation"] = rotation_system
    return graph

def transform(x):
    #takes x from [-pi, pi] and puts it in [0,pi]
    if x >= 0:
        return x
    if x < 0:
        return 2 * np.pi + x
    


def is_clockwise(graph,face, average):
    #given a face (with respect to the rotation system computed), determine if it belongs to a the orientation assigned to bounded faces
    angles = [transform(float(np.arctan2(graph.node[x]["pos"][0] - average[0], graph.node[x]["pos"][1] - average[1])))  for x in face]
    first = min(angles)
    rotated = [x - first for x in angles]
    next_smallest = min([x for x in rotated if x != 0])
    ind = rotated.index(0)
    if rotated[(ind + 1)% len(rotated)] == next_smallest:
        return False
    else:
        return True

def cycle_around_face(graph, e):
    face = list([e[0], e[1]])
    last_point = e[1]
    current_point = graph.node[e[1]]["rotation"][e[0]]
    next_point = current_point
    while next_point != e[0]:
        face.append(current_point)
        next_point = graph.node[current_point]["rotation"][last_point]
        last_point = current_point
        current_point = next_point
    return face


def compute_face_data(graph):
    #graph must already have a rotation_system
    faces = []
    #faces will stored as sets of vertices

    for e in graph.edges():
        #need to make sure you get both possible directions for each edge..
        
        face = cycle_around_face(graph, e)
        faces.append(tuple(face))
        face = cycle_around_face(graph, [ e[1], e[0]])
        faces.append(tuple(face))
    #detect the unbounded face based on orientation
    bounded_faces = []
    for face in faces:
        run_sum = np.array([0,0]).astype('float64')
        for x in face:
            run_sum += np.array(graph.node[x]["pos"]).astype('float64')
        average = run_sum / len(face)
        if is_clockwise(graph,face, average):
            bounded_faces.append(face)
    faces_set = [frozenset(face) for face in bounded_faces]
    graph.graph["faces"] = set(faces_set)
    return graph

def compute_all_faces(graph):
        #graph must already have a rotation_system
    faces = []
    #faces will stored as sets of vertices

    for e in graph.edges():
        #need to make sure you get both possible directions for each edge..
        
        face = cycle_around_face(graph, e)
        faces.append(tuple(face))
        face = cycle_around_face(graph, [ e[1], e[0]])
        faces.append(tuple(face))
    
    #This overcounts, have to delete cyclic repeats now:
        
    sorted_faces = list(set([tuple(canonical_order(graph,x)) for x in faces]))
    cleaned_faces = [ tuple([ y for y in F]) for F in sorted_faces]
    graph.graph["faces"] = cleaned_faces
    return graph

def canonical_order(graph, face):
    '''
    Outputs the coordinates of the nodes of the face in a canonical order
    in particular, the first one is the lex-min. 
    
    You need to use the graph structure to make this work
    '''
    
    lex_sorted_nodes = sorted(face)
    first_node = lex_sorted_nodes[0]
    cycle_sorted_nodes = [first_node]
    local_cycle = nx.subgraph( graph, face)

    #Compute the second node locally based on angle orientation
    
    v = first_node
    locations = []
    neighbor_list = list(local_cycle.neighbors(v))
    for w in neighbor_list:
        locations.append(graph.node[w]["pos"] - graph.node[v]["pos"])
    angles = [float(np.arctan2(x[1], x[0])) for x in locations]
    neighbor_list.sort(key=dict(zip(neighbor_list, angles)).get)
    
    second_node = neighbor_list[0]
    cycle_sorted_nodes.append(second_node)
    ##Now compute a canonical ordering of local_cycle, clockwise, starting
    ##from first_node
    
  
    while len(cycle_sorted_nodes) < len(lex_sorted_nodes):
        
        v = cycle_sorted_nodes[-1]
        neighbor_list = list(local_cycle.neighbors(v))
        neighbor_list.remove(cycle_sorted_nodes[-2])
        cycle_sorted_nodes.append(neighbor_list[0])
    
    return cycle_sorted_nodes


def delete_copies_up_to_permutation(array):
    '''
    Given an array of tuples, return an array consisting of one representative
    for each element in the orbit of the reordering action.
    '''
    
    cleaned_array = list(set([tuple(canonical_order(x)) for x in array]))
    
    return cleaned_array

def face_refine(graph):
    #graph must already have the face data computed
    #this adds a vetex in the middle of each face, and connects that vertex to the edges of that face...
    
    for face in graph.graph["faces"]:
        graph.add_node(face)
        location = np.array([0,0]).astype("float64")
        for v in face:
            graph.add_edge(face, v)
            location += graph.node[v]["pos"].astype("float64")
        graph.node[face]["pos"] = location / len(face)
    return graph

def edge_refine(graph):
    edge_list = list(graph.edges())
    for e in edge_list:
        graph.remove_edge(e[0],e[1])
        graph.add_node(str(e))
        location = np.array([0,0]).astype("float64")
        for v in e:
            graph.add_edge(str(e), v)
            location += graph.node[v]["pos"].astype("float64")
        graph.node[str(e)]["pos"] = location / 2
    return graph

def refine(graph):
    graph = compute_rotation_system(graph)
    graph = compute_face_data(graph)
    graph = face_refine(graph)
    return graph

def depth_k_refine(graph,k):
    graph.name = graph.name + str("refined_depth") + str(k)
    for i in range(k):
        graph = refine(graph)
    return graph

def depth_k_barycentric(graph, k):
    graph.name = graph.name + str("refined_depth") + str(k)
    for i in range(k):
        graph = barycentric_subdivision(graph)
    return graph

def barycentric_subdivision(graph):
    #graph must already have the face data computed
    #this adds a vetex in the middle of each face, and connects that vertex to the edges of that face...
    graph = edge_refine(graph)
    graph = refine(graph)
    return graph
    

def restricted_planar_dual(graph):
    #computes dual without unbounded face
    graph = compute_rotation_system(graph)
    graph = compute_face_data(graph)
    dual_graph = nx.Graph()
    for face in graph.graph["faces"]:
        dual_graph.add_node(face)
        location = np.array([0,0]).astype("float64")
        for v in face:
            location += graph.node[v]["pos"].astype("float64")
        dual_graph.node[face]["pos"] = location / len(face)
    ##handle edges
    for e in graph.edges():
        for face in graph.graph["faces"]:
            for face2 in graph.graph["faces"]:
                if face != face2:
                    if (e[0] in face) and (e[1] in face) and (e[0] in face2) and (e[1] in face2):
                        dual_graph.add_edge(face, face2)
    return dual_graph



def draw_with_location(graph,c='k',ns=100,w=3,ec='b'):
#    for x in graph.nodes():
#        graph.node[x]["pos"] = [graph.node[x]["X"], graph.node[x]["Y"]]

    nx.draw(graph, pos=nx.get_node_attributes(graph, 'pos'), node_size = ns, width = w, node_color=c,edge_color=ec)


graph = compute_rotation_system(g)
graph = compute_face_data(graph) 

dual = restricted_planar_dual(graph)
plt.figure()
draw_with_location(graph,'b',50,1,'b')
draw_with_location(dual,'r',50,1,'r')
plt.show()
## 
#m= 3
#graph = nx.grid_graph([m,m])
#graph.name = "grid_size:" + str(m)
#for x in graph.nodes():
#    
#    graph.node[x]["pos"] = np.array([x[0], x[1]])
#
###graph = depth_k_refine(graph,0)
##graph = depth_k_barycentric(graph, 4)
#draw_with_location(graph)
#graph = compute_rotation_system(graph)
#graph = compute_face_data(graph) 
##print(len(graph.graph["faces"]))
##
#dual = restricted_planar_dual(graph)
#draw_with_location(dual)
