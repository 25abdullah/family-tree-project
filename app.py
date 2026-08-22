import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from collections import deque

st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
    /* Bigger buttons and labels so nothing is hard to find or read. */
    div.stButton > button, div.stFormSubmitButton > button {
        font-size: 1.05rem;
        font-weight: 600;
        padding: 0.65rem 1.4rem;
        width: 100%;
    }
    label {
        font-size: 1rem !important;
        font-weight: 600 !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1rem;
        padding: 0.6rem 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Core data functions (framework-agnostic) ----------

def add_person(name, tree, next_id):
    this_id = next_id
    tree[this_id] = {"name": name, "children": [], "parents": [], "spouse": []}
    next_id += 1
    return this_id, next_id

def add_parent_child(parent_id, child_id, tree):
    tree[parent_id]["children"].append(child_id)
    tree[child_id]["parents"].append(parent_id)

def add_spouse(spouse_one_id, spouse_two_id, tree):
    tree[spouse_one_id]["spouse"].append(spouse_two_id)
    tree[spouse_two_id]["spouse"].append(spouse_one_id)

def delete_person(person_id, tree):
    """Remove person_id from every connected person's record, then remove
    their own entry. Symmetric cleanup — mirrors how edges were added."""
    for parent_id in tree[person_id]["parents"]:
        tree[parent_id]["children"].remove(person_id)
    for child_id in tree[person_id]["children"]:
        tree[child_id]["parents"].remove(person_id)
    for spouse_id in tree[person_id]["spouse"]:
        tree[spouse_id]["spouse"].remove(person_id)
    del tree[person_id]

def get_neighbors(person_id, mode, tree):
    if mode == 'all':
        return tree[person_id]['children'] + tree[person_id]['spouse'] + tree[person_id]['parents']
    elif mode == 'children':
        return tree[person_id]['children']
    elif mode == 'parents':
        return tree[person_id]['parents']

def bfs(tree, start_node, mode):
    queue = deque([start_node])
    best_neighbor = {start_node: None}
    while queue:
        current_node = queue.popleft()
        for neighbor in get_neighbors(current_node, mode, tree):
            if neighbor not in best_neighbor.keys():
                queue.append(neighbor)
                best_neighbor[neighbor] = current_node
    return best_neighbor

def get_path(start_node, end_node, neighbor_dict):
    path_look_up = []
    while True:
        if end_node is None:
            break
        path_look_up.append(end_node)
        end_node = neighbor_dict[end_node]
    path_look_up.reverse()
    return path_look_up

def recursive_distance_calculation(start_node, end_node, neighbor_dict):
    if start_node == end_node:
        return 0
    if neighbor_dict[end_node] == start_node:
        return 1
    else:
        return 1 + recursive_distance_calculation(
            start_node, neighbor_dict[end_node], neighbor_dict
        )

def validate_parent_link(parent_id, child_id, tree):
    """Return an error message if making parent_id a parent of child_id is
    invalid, else None. Kept framework-agnostic (no Streamlit calls)."""
    p_name = tree[parent_id]["name"]
    c_name = tree[child_id]["name"]
    if parent_id == child_id:
        return "A person can't be their own parent."
    if len(tree[child_id]["parents"]) >= 2:
        return f"{c_name} already has two parents."
    if parent_id in tree[child_id]["parents"]:
        return f"{p_name} is already {c_name}'s parent."
    if child_id in bfs(tree, parent_id, 'parents'):
        return f"That would make {c_name} their own ancestor."
    if child_id in tree[parent_id]["spouse"]:
        return f"{p_name} and {c_name} are married, so they can't be parent and child."
    return None

def compute_generation(person_id, tree):
    if (not tree[person_id]['parents']) and (not tree[person_id]['spouse']):
        return 0
    elif (not tree[person_id]['parents']) and all(not tree[s]['parents'] for s in tree[person_id]['spouse']):
        return 0
    elif tree[person_id]['parents']:
        return 1 + max(compute_generation(p, tree) for p in tree[person_id]['parents'])
    elif tree[person_id]['spouse']:
        return max(compute_generation(s, tree) for s in tree[person_id]['spouse'])
    return 0

def create_hierchal_map(tree, highlight_path=None):
    generations = {key: compute_generation(key, tree) for key in tree.keys()}
    # Width should track how crowded the busiest single generation is;
    # height should track how many generations deep the tree goes.
    if generations:
        widest_generation = max(
            list(generations.values()).count(g) for g in set(generations.values())
        )
        depth = max(generations.values()) - min(generations.values()) + 1
    else:
        widest_generation, depth = 1, 1
    # Floors keep small trees readable; ceilings stop a very wide or deep tree
    # from producing a figure so large it gets scaled down to illegibility.
    fig, ax = plt.subplots(
        figsize=(
            min(14, max(7, widest_generation * 2)),
            min(12, max(6, depth * 2.2)),
        )
    )
    ax.axis('equal')
    G = nx.Graph()
    parent_child_edges = []
    spouse_edges = []
    for key in tree.keys():
        G.add_node(key, layer=generations[key])
    for key, value in tree.items():
        for parent in value['parents']:
            G.add_edge(parent, key)
            parent_child_edges.append((parent, key))
    for key, value in tree.items():
        for spouse in value['spouse']:
            if (key, spouse) not in spouse_edges and (spouse, key) not in spouse_edges:
                G.add_edge(spouse, key)
                spouse_edges.append((spouse, key))
    pos = nx.multipartite_layout(G, subset_key="layer", align="horizontal")
    labels = {node: f"{tree[node]['name']} (id {node})" for node in G.nodes()}
    # Spread nodes further apart (both axes) so labels don't overlap or crowd.
    flipped_pos = {node: [-v[0] * 2.2, -1 * v[1] * 2.2] for node, v in pos.items()}
    nx.draw_networkx_edges(G, flipped_pos, edgelist=parent_child_edges, ax=ax,
                           edge_color='gray', width=2)
    nx.draw_networkx_edges(G, flipped_pos, edgelist=spouse_edges, ax=ax,
                           edge_color='mediumvioletred', width=2, style='dashed')
    # Highlight goes under the nodes so the circles stay legible on top of it.
    if highlight_path and len(highlight_path) > 1:
        path_edges = list(zip(highlight_path, highlight_path[1:]))
        nx.draw_networkx_edges(G, flipped_pos, edgelist=path_edges,
                               width=5, edge_color='red', ax=ax)
    nx.draw_networkx_nodes(G, flipped_pos, ax=ax, node_color='lightblue',
                           node_size=1300)
    nx.draw_networkx_labels(G, flipped_pos, labels=labels, ax=ax, font_size=9,
                            font_weight='bold')
    # Give labels room so they don't get clipped at the figure's edges.
    ax.margins(0.2)
    fig.tight_layout()
    return fig

# ---------- Streamlit helpers (read session_state) ----------

def get_name(id):
    if id in st.session_state.tree:
        return st.session_state.tree[id]["name"]
    else:
        return "something went wrong."

def get_label(id):
    return f"{get_name(id)} (id {id})"

# ---------- Session state ----------

if "tree" not in st.session_state:
    st.session_state.tree = {}
    st.session_state.next_id = 0
    st.session_state.highlight_path = None

st.title("Family Tree Builder")

with st.expander("How to use this. Read me first.", expanded=True):
    st.markdown(
        """
### Scroll down to see your tree

Your tree is drawn below these instructions. Scroll down to see all of it. You
can close this box using the arrow above once you have read it.

---

The tabs are numbered in a rough order to follow, but you can move between them
however you like. You just need at least two people before you can connect
anyone. The tree on the right redraws every time you add something.

**1. Add people.** Type a name and click the button. Repeat for everyone.

**2. Parents.** Pick the child, then their parents. Everyone can have up to two
parents. Adding two parents together does NOT mark them as married. To do that,
use the Married couples tab.

**3. Married couples.** Pick two people to mark them as married. Each person can
have one spouse only.

**4. How are they related?** Choose two people and click *Show the connection*.
You get the chain of people linking them, how many steps apart they are, and
that same chain drawn in red on the tree.

**5. Fix a mistake.** Remove one person, or clear everyone and start over.

On the tree, grey lines connect parents to children. Dashed pink lines connect
married couples.

Each person gets a number, like *Mom (id 3)*. Use it to tell two people apart
when they have the same name.

The app blocks things that make no sense, like someone being their own
grandparent, and tells you why. It catches what it can, but family trees get
complicated, so it will miss some cases. If the tree looks wrong, remove the
person and add them again.

---

**Before you start.** Your tree is not saved. Refreshing the page or closing the
tab clears it, so finish in one sitting or take a screenshot. If you see a
loading screen when you first open the page, the app was asleep. Give it about
thirty seconds. Use a laptop or desktop. On a phone the tree gets squeezed into
a narrow strip.
        """
    )

left, right = st.columns([1, 2])

with left:
    tree = st.session_state.tree
    tab_add, tab_parent, tab_spouse, tab_path, tab_delete = st.tabs(
        ["1. Add people", "2. Parents", "3. Married couples", "4. How are they related?", "5. Fix a mistake"]
    )

    # --- Add Person ---
    with tab_add:
        with st.form(key="add-person-form", clear_on_submit=True):
            person_name = st.text_input("Name")
            add_person_submit = st.form_submit_button("Add person")
        if add_person_submit:
            if person_name:
                new_id, st.session_state.next_id = add_person(
                    person_name, tree, st.session_state.next_id
                )
                st.success(f"Added {person_name} (id {new_id})")
            else:
                st.error("Enter a name first.")

    # --- Add Parent-Child ---
    with tab_parent:
        st.markdown(
            "**Pick the child first**, then their parents. If you know both, add "
            "them together in this one step. If you only know one, leave "
            "*Parent 2* set to none."
        )
        if len(tree) < 2:
            st.info("Add at least 2 people in tab 1 first.")
        else:
            with st.form(key="add-parent-child-form"):
                options = list(tree.keys())
                child_id = st.selectbox("Child", options, format_func=get_label, key="pc_child")
                parent_one = st.selectbox("Parent 1", options, index=1, format_func=get_label, key="pc_parent1")
                parent_two = st.selectbox(
                    "Parent 2 (optional)",
                    [None] + options,
                    format_func=lambda x: "— none —" if x is None else get_label(x),
                    key="pc_parent2",
                )
                pc_submit = st.form_submit_button("Connect these parents")

            if pc_submit:
                # Collect the parents actually chosen (Parent 2 may be skipped).
                chosen_parents = [parent_one]
                if parent_two is not None:
                    chosen_parents.append(parent_two)

                error = None
                if parent_two is not None and parent_one == parent_two:
                    error = "Parent 1 and Parent 2 are the same person."
                elif len(tree[child_id]["parents"]) + len(chosen_parents) > 2:
                    error = (
                        f"{get_name(child_id)} would end up with more than two parents."
                    )
                elif parent_two is not None and (
                    parent_two in bfs(tree, parent_one, 'parents')
                    or parent_one in bfs(tree, parent_two, 'parents')
                ):
                    error = (
                        f"{get_name(parent_one)} and {get_name(parent_two)} can't both be "
                        f"{get_name(child_id)}'s parents, because one is already the other's ancestor."
                    )
                else:
                    # Validate every chosen parent link before adding any of them.
                    for p in chosen_parents:
                        error = validate_parent_link(p, child_id, tree)
                        if error:
                            break

                if error:
                    st.error(error)
                else:
                    for p in chosen_parents:
                        add_parent_child(p, child_id, tree)
                    names = " and ".join(get_name(p) for p in chosen_parents)
                    st.success(f"Added: {names} → {get_name(child_id)}")

    # --- Add Spouse ---
    with tab_spouse:
        if len(tree) < 2:
            st.info("Add at least 2 people in tab 1 first.")
        else:
            with st.form(key="add-spouse-form"):
                options = list(tree.keys())
                spouse_one = st.selectbox("Spouse 1", options, format_func=get_label, key="sp_one")
                spouse_two = st.selectbox("Spouse 2", options, index=1, format_func=get_label, key="sp_two")
                sp_submit = st.form_submit_button("Add spouse")
            if sp_submit:
                if spouse_one == spouse_two:
                    st.error("A person can't be their own spouse.")
                elif spouse_two in tree[spouse_one]["spouse"]:
                    st.error(f"{get_name(spouse_one)} and {get_name(spouse_two)} are already spouses.")
                elif tree[spouse_one]["spouse"]:
                    st.error(f"{get_name(spouse_one)} already has a spouse.")
                elif tree[spouse_two]["spouse"]:
                    st.error(f"{get_name(spouse_two)} already has a spouse.")
                elif spouse_two in tree[spouse_one]["children"] or spouse_two in tree[spouse_one]["parents"]:
                    st.error(f"{get_name(spouse_one)} and {get_name(spouse_two)} are parent and child, so they can't be married.")
                elif (
                    spouse_two in bfs(tree, spouse_one, 'parents')
                    or spouse_one in bfs(tree, spouse_two, 'parents')
                ):
                    st.error(f"{get_name(spouse_one)} and {get_name(spouse_two)} are ancestor and descendant, so they can't be married.")
                else:
                    add_spouse(spouse_one, spouse_two, tree)
                    st.success(f"Added: {get_name(spouse_one)} ⇔ {get_name(spouse_two)}")

    # --- Find Path ---
    with tab_path:
        if len(tree) < 2:
            st.info("Add at least 2 people in tab 1 first.")
        else:
            with st.form(key="find-path-form"):
                options = list(tree.keys())
                start_id = st.selectbox("From", options, format_func=get_label, key="path_start")
                end_id = st.selectbox("To", options, index=1, format_func=get_label, key="path_end")
                path_submit = st.form_submit_button("Show the connection")
            if path_submit:
                if start_id == end_id:
                    st.info("That is the same person twice. Pick two different people.")
                    st.session_state.highlight_path = None
                else:
                    neighbor_dict = bfs(tree, start_id, 'all')
                    if end_id not in neighbor_dict:
                        st.error(f"{get_name(start_id)} and {get_name(end_id)} are not connected to each other yet.")
                        st.session_state.highlight_path = None
                    else:
                        path = get_path(start_id, end_id, neighbor_dict)
                        distance = recursive_distance_calculation(start_id, end_id, neighbor_dict)
                        readable = " → ".join(get_label(pid) for pid in path)
                        st.session_state.highlight_path = path
                        st.success(f"Connection: {readable}")
                        st.metric("Steps apart", distance)
                        print(f"Path from {get_name(start_id)} to {get_name(end_id)}: {readable} (distance {distance})")

            if st.session_state.highlight_path:
                if st.button("Hide the red line"):
                    st.session_state.highlight_path = None
                    st.rerun()

    # --- Delete Person ---
    with tab_delete:
        if len(tree) == 0:
            st.info("Nobody to remove yet.")
        else:
            with st.form(key="delete-person-form"):
                options = list(tree.keys())
                delete_id = st.selectbox("Person", options, format_func=get_label, key="delete_person")
                delete_submit = st.form_submit_button("Remove this person")
            if delete_submit:
                deleted_name = get_name(delete_id)
                delete_person(delete_id, tree)
                # Any cached path may reference the deleted person — discard it
                # rather than try to patch it, since removing a person can
                # break connectivity between other people too.
                st.session_state.highlight_path = None
                st.success(f"Removed {deleted_name}.")

        st.divider()
        st.write("Want to wipe everything and start over?")
        if st.button("Clear the whole tree"):
            st.session_state.tree = {}
            st.session_state.next_id = 0
            st.session_state.highlight_path = None
            st.rerun()

with right:
    st.subheader("Your family tree")
    if st.session_state.tree:
        count = len(st.session_state.tree)
        st.caption(f"{count} {'person' if count == 1 else 'people'} in the tree")
        fig = create_hierchal_map(st.session_state.tree, st.session_state.highlight_path)
        st.pyplot(fig)
        st.caption(
            "Grey lines connect parents to children. Dashed pink lines connect "
            "married couples. A red line shows a connection you searched for."
        )
    else:
        st.info("Start with tab 1 and add a person. Your tree will appear here.")