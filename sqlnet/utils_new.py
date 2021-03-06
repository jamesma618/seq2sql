# -*- coding: utf-8 -*-
import json
from lib.dbengine import DBEngine
import re
import numpy as np
from os import listdir
import re
import sys
from nltk import word_tokenize
PATH_NL2SQL = 'New_Data/Initial'
TRAIN_EXT = '/train'
DEV_EXT = '/dev'
TABLE_EXT = '/tables'


def lower_keys(x):
    if isinstance(x, list):
        return [lower_keys(v) for v in x]
    elif isinstance(x, dict):
        return dict((k.lower(), lower_keys(v)) for k, v in x.iteritems())
    else:
        return x

def get_main_file_name(file_path):
    prefix_pattern = re.compile('(New_Data/Initial/.*/)(.*)(\.json)')
    if prefix_pattern.search(file_path):
        return prefix_pattern.search(file_path).group(2)
    return None

def get_main_table_name(file_path):
    prefix_pattern = re.compile('(New_Data/Initial/.*/)(.*)(_table\.json)')
    if prefix_pattern.search(file_path):
        return prefix_pattern.search(file_path).group(2)
    return None

def get_tables_for_sql(orig_path, train=0):
    TABLE_PATH = orig_path + TABLE_EXT
    tables = [TABLE_PATH + '/' + file for file in listdir(TABLE_PATH)]
    table_names  = [get_main_table_name(file) for file in tables]

    if train == 0:
        SQL_PATH = PATH_NL2SQL + TRAIN_EXT
    else:
        SQL_PATH = PATH_NL2SQL + DEV_EXT
    sql_data = [get_main_file_name(SQL_PATH + '/' + file) for file in listdir(SQL_PATH)]

    table_data = [TABLE_PATH + '/' + file  + '_table.json' for file in table_names if file in sql_data]
    sql_data = [SQL_PATH + '/' + file + '.json'for file in sql_data]

    return sorted(sql_data), sorted(table_data) 
def safe_list_get(lst, index, default=None):
    try:
        return lst[index]
    except IndexError:
        return default

def get_table_names_from_query(query_tok, select=False):
    table_names = []
    if select:
        indices = [i + 1 for i, x in enumerate(query_tok) if x.lower() == "from" ]
    else:
        indices = [i + 1 for i, x in enumerate(query_tok) if x.lower() == "from" or x.lower() == 'join']
    table_names = [query_tok[index] for index in indices]
    return list(set(table_names))

def clean_table_data(json_data, use_small=False):
    table_data = {}
    for database_name in json_data.keys():
        database = {}
        for table in json_data[database_name]:
            table_info = {}
            table_info['header'] = [col['column_name'].lower() for col in table['col_data']]
            table_info['header_tok'] = [word_tokenize(col.lower()) for col in table_info['header']]
            table_info['rows'] = [] #TODO: fill in with database contents
            table_info['page_title'] = '' #TODO: do I need anything for this?
            table_info['section_title'] = ''
            table_info['types'] = [col['data_type'] for col in table['col_data']]
            database[table['table'].lower()] = table_info
        table_data[database_name] = database
    return table_data

def convert_colnames_colnum(cleaned_data_item, table_data, col_names, select=False):
    # names of columns --> column_numbers!
    col_num =[]
    if select:
        diff_tables = cleaned_data_item['selected_table'][0]
    else:
        diff_tables = cleaned_data_item['table_ids'][0]
    print 'selected_col_names', col_names
    for table in diff_tables:
        col_num_small = []
        table_cols = table_data[table]['header']
        print 'table_cols, ', table_cols
        for col in col_names:
            if col == '*':
                col_num.append(range(len(table_cols)))
                break
            if col in table_cols:
                col_num_small.append(table_cols.index(col))
        if len(col_num_small) > 0:
            col_num.append(col_num_small)
    print 'col_num', col_num
    return col_num

def get_select_indices(cleaned_data_item, table_data, agg_code=0):
    query_tok = cleaned_data_item['query_tok'][0]
    col_names = query_tok[query_tok.index('select') + 1:query_tok.index('from')]
    to_delete = ['max', 'min', 'count', 'sum', 'avg', 'distinct', ',', '(', ')']
    for item in to_delete:
        try:
            col_names.remove(item)
        except ValueError:
            pass
    pattern = re.compile('(t\d+\.)(.*)')
    for i, item in enumerate(col_names):
        if pattern.search(item) is not None:
            col_names[i] = pattern.search(item).group(2)

    # names of columns --> column_numbers!
    return convert_colnames_colnum(cleaned_data_item, table_data, col_names, select=True)
    # col_num =[]
    # diff_tables = cleaned_data_item['selected_table'][0]
    # for table in diff_tables:
    #     col_num_small = []
    #     table_cols = table_data[table]['header']
    #     print 'table_cols ',table_cols
    #     for col in col_names:
    #         if col == '*':
    #             col_num.append(range(len(table_cols)))
    #             break
    #         if col in table_cols:
    #             col_num_small.append(table_cols.index(col))
    #     if len(col_num_small) > 0:
    #         col_num.append(col_num_small)
    # return col_num
    #print json.dumps(table_data, indent=4)



    

def check_for_agg(query):
    agg_ops = ['(max)\((.+?)\)', '(min)\((.+?)\)', '(count)\((.+?)\)', '(sum)\((.+?)\)', '(avg)\((.+?)\)']
    for x, agg in enumerate(agg_ops):
        pattern = re.compile(agg)
        if pattern.search(query) is not None:
            return x + 1
    return 0


#NOTE: should be only the table_data that is relevant to this question
def add_sql_item_to_data(cleaned_data_item, table_data):
    agg_code = check_for_agg(cleaned_data_item['query'][0])
    select_indices = get_select_indices(cleaned_data_item, table_data, agg_code=agg_code)
    conds = [] # TODO
    cleaned_data_item['sql'] = {'conds': conds, 'sel': select_indices, 'agg_code': agg_code}
    
    

def clean_sql_data(json_data, table_data, use_small=False):
    #NOTE: should only be called after clean_table_data
    sql_data = []
    count = 0
    exit = False
    for database in json_data:
        for item in database['data']:
            if count > 50 and use_small:
                exit = True
                break
            cleaned_data = {}
            cleaned_data['database_name'] = database['database_name']
            cleaned_data['question']= item['sqa']['question']
            cleaned_data['query']= item['sqa']['sql']
            cleaned_data['query_tok'] = [word_tokenize(query.lower()) for query in cleaned_data['query']]
            cleaned_data['table_ids'] = [get_table_names_from_query(query_tok,select=False) for query_tok in cleaned_data['query_tok']]
            cleaned_data['selected_table'] = [get_table_names_from_query(query_tok, select=True) for query_tok in cleaned_data['query_tok']]
            cleaned_data['question_tok'] = [word_tokenize(question.lower()) for question in cleaned_data['question']]
            sql_data.append(cleaned_data)
            count += 1
        if exit:
            break
    for item in sql_data:
        specific_table_data = {} 
        for table in item['table_ids'][0]:
            specific_table_data[table] = table_data[item['database_name']][table]
        add_sql_item_to_data(item, specific_table_data)
    return sql_data
        #_ed_data['query_2'] = database['data']['sqa']['sql'][1]
        #eaned_data['query_3'] = safe_list_get(database['data']['sqa']['sql'], 2)


def load_data_new(sql_paths, table_paths, use_small=False):
    if not isinstance(sql_paths, list):
        sql_paths = (sql_paths, )
    if not isinstance(table_paths, list):
        table_paths = (table_paths, )
    sql_data = []
    table_data = {}
    for i, SQL_PATH in enumerate(sql_paths):
        if use_small and i >= 2:
            break
        print "Loading data from %s"%SQL_PATH
        with open(SQL_PATH) as inf:
            file_name = get_main_file_name(SQL_PATH)
            if file_name:
                sql_data.append(lower_keys(json.load(inf)))
                sql_data[i]['database_name'] = file_name
                
    for i, TABLE_PATH in enumerate(table_paths):
        if use_small and i >= 2:
            break
        print "Loading data from %s"%TABLE_PATH
        with open(TABLE_PATH) as inf:
            file_name = get_main_table_name(TABLE_PATH)
            if file_name:
                table_data[file_name] = lower_keys(json.load(inf))
    return sql_data, table_data

def load_data(sql_paths, table_paths, use_small=False, tao=False):
    if not isinstance(sql_paths, list):
        sql_paths = (sql_paths, )
    if not isinstance(table_paths, list):
        table_paths = (table_paths, )
    sql_data = []
    table_data = {}
    max_col_num = 0
    for SQL_PATH in sql_paths:
        print "Loading data from %s"%SQL_PATH
        with open(SQL_PATH) as inf:
            if not tao: 
                for idx, line in enumerate(inf):
                    if use_small and idx >= 1000:
                        break
                    sql = json.loads(line.strip())
                    sql_data.append(sql)
            else:
                sql = json.loads(inf)
                sql_data.append(sql)

    for TABLE_PATH in table_paths:
        print "Loading data from %s"%TABLE_PATH
        with open(TABLE_PATH) as inf:
            if not tao:
                for line in inf:
                    tab = json.loads(line.strip())
                    table_data[tab[u'id']] = tab
            else:
                tab = json.loads(inf)
                table_data[tab[u'id']] = tab

    for sql in sql_data:
        assert sql[u'table_id'] in table_data
    return sql_data, table_data

def load_dataset_new(dataset_id, use_small=False):
    print "Loading from nl2sql Yale dataset"
    # Load training data  
    sql_paths_train, table_paths_train  = get_tables_for_sql(PATH_NL2SQL, train=0)
    train_sql_data, train_table_data = load_data_new(sql_paths_train, table_paths_train, \
        use_small=use_small)
    train_table_data = clean_table_data(train_table_data, use_small=use_small)
    train_sql_data = clean_sql_data(train_sql_data, train_table_data, use_small=use_small)
    # Load Dev Data
    sql_paths_val, table_paths_val  = get_tables_for_sql(PATH_NL2SQL, train=1)
    val_sql_data, val_table_data = load_data_new(sql_paths_val, table_paths_val, \
        use_small=use_small)
    val_table_data = clean_table_data(val_table_data, use_small=use_small)
    val_sql_data = clean_sql_data(val_sql_data, val_table_data, use_small=use_small)
    
    ##TODO
    test_sql_data, test_table_data = {}, {}
    return train_sql_data, train_table_data, val_sql_data, val_table_data,\
            test_sql_data, test_table_data

def load_dataset(dataset_id, use_small=False):
    if dataset_id == 0:
        print "Loading from original dataset"
        sql_data, table_data = load_data('data/train_tok.jsonl',
                'data/train_tok.tables.jsonl', use_small=use_small)
        val_sql_data, val_table_data = load_data('data/dev_tok.jsonl',
                'data/dev_tok.tables.jsonl', use_small=use_small)
        test_sql_data, test_table_data = load_data('data/test_tok.jsonl',
                'data/test_tok.tables.jsonl', use_small=use_small)
        TRAIN_DB = 'data/train.db'
        DEV_DB = 'data/dev.db'
        TEST_DB = 'data/test.db'
    elif dataset_id == 1:
        print "Loading from re-split dataset"
        sql_data, table_data = load_data('data_resplit/train.jsonl',
                'data_resplit/tables.jsonl', use_small=use_small)
        val_sql_data, val_table_data = load_data('data_resplit/dev.jsonl',
                'data_resplit/tables.jsonl', use_small=use_small)
        test_sql_data, test_table_data = load_data('data_resplit/test.jsonl',
                'data_resplit/tables.jsonl', use_small=use_small)
        TRAIN_DB = 'data_resplit/table.db'
        DEV_DB = 'data_resplit/table.db'
        TEST_DB = 'data_resplit/table.db'
    else:
        print "Loading from nl2sql Yale dataset"
        # Load training data  
        sql_paths_train, table_paths_train  = get_tables_for_sql(PATH_NL2SQL, train=0)
        train_sql_data, train_table_data = load_data_new(sql_paths_train, table_paths_train, \
            use_small=use_small)
        # Load Dev Data
        sql_paths_val, table_paths_val  = get_tables_for_sql(PATH_NL2SQL, train=1)
        val_sql_data, val_table_data = load_data_new(sql_paths_train, table_paths_train, \
            use_small=use_small)
        test_sql_data, test_table_data = {}, {}
        TRAIN_DB, DEV_DB, TEST_DB = None, None, None
        #sql_data, table_data = load_data(PATH_NL2SQL + '/train.json', use_small=use_small)


    return train_sql_data, train_table_data, val_sql_data, val_table_data,\
            test_sql_data, test_table_data, TRAIN_DB, DEV_DB, TEST_DB

def best_model_name(args, for_load=False):
    new_data = 'new' if args.dataset > 0 else 'old'
    mode = 'seq2sql' if args.baseline else 'sqlnet'
    if for_load:
        use_emb = use_rl = ''
    else:
        use_emb = '_train_emb' if args.train_emb else ''
        use_rl = 'rl_' if args.rl else ''
    use_ca = '_ca' if args.ca else ''

    agg_model_name = 'saved_model/%s_%s%s%s.agg_model'%(new_data,
            mode, use_emb, use_ca)
    sel_model_name = 'saved_model/%s_%s%s%s.sel_model'%(new_data,
            mode, use_emb, use_ca)
    cond_model_name = 'saved_model/%s_%s%s%s.cond_%smodel'%(new_data,
            mode, use_emb, use_ca, use_rl)

    if not for_load and args.train_emb:
        agg_embed_name = 'saved_model/%s_%s%s%s.agg_embed'%(new_data,
                mode, use_emb, use_ca)
        sel_embed_name = 'saved_model/%s_%s%s%s.sel_embed'%(new_data,
                mode, use_emb, use_ca)
        cond_embed_name = 'saved_model/%s_%s%s%s.cond_embed'%(new_data,
                mode, use_emb, use_ca)
        return agg_model_name, sel_model_name, cond_model_name,\
                agg_embed_name, sel_embed_name, cond_embed_name
    else:
        return agg_model_name, sel_model_name, cond_model_name


def to_batch_seq(sql_data, table_data, idxes, st, ed, ret_vis_data=False):
    q_seq = []
    col_seq = []
    col_num = []
    ans_seq = []
    query_seq = []
    gt_cond_seq = []
    vis_seq = []
    #print json.dumps(table_data, indent=4)
    #print json.dumps(sql_data, indent=4)
    for i in range(st, ed):
        sql = sql_data[idxes[i]]
        #print json.dumps(sql, indent=4)
        q_seq.append(sql['question_tok'][0]) # getting the first question
        #get the corresponding column header names
        header_names = []
        table_col_length = []
        for table in table_data[sql['database_name']][sql[table_ids][0]]:
            header_names.append(table['header_tok'])
            table_col_length.append(len(table['header']))
        col_seq.append(header_names) 
        col_num.append(table_col_length)
        ans_seq.append((sql['sql']['agg'],
            sql['sql']['sel'], 
            len(sql['sql']['conds']),
            tuple(x[0] for x in sql['sql']['conds']),
            tuple(x[1] for x in sql['sql']['conds'])))
        query_seq.append(sql['query_tok'])
        gt_cond_seq.append(sql['sql']['conds'])
        vis_seq.append((sql['question'],
            table_data[sql['table_id']]['header'], sql['query']))
    if ret_vis_data:
        return q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq, vis_seq
    else:
        return q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq

def to_batch_query(sql_data, idxes, st, ed):
    query_gt = []
    table_ids = []
    for i in range(st, ed):
        query_gt.append(sql_data[idxes[i]]['sql'])
        table_ids.append(sql_data[idxes[i]]['table_id'])
    return query_gt, table_ids

def epoch_train(model, optimizer, batch_size, sql_data, table_data, pred_entry):
    model.train()
    perm=np.random.permutation(len(sql_data))
    cum_loss = 0.0
    st = 0
    while st < len(sql_data):
        ed = st+batch_size if st+batch_size < len(perm) else len(perm)

        q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq = \
                to_batch_seq(sql_data, table_data, perm, st, ed)
        gt_where_seq = model.generate_gt_where_seq(q_seq, col_seq, query_seq)
        gt_sel_seq = [x[1] for x in ans_seq]
        score = model.forward(q_seq, col_seq, col_num, pred_entry,
                gt_where=gt_where_seq, gt_cond=gt_cond_seq, gt_sel=gt_sel_seq)
        loss = model.loss(score, ans_seq, pred_entry, gt_where_seq)
        cum_loss += loss.data.cpu().numpy()[0]*(ed - st)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        st = ed

    return cum_loss / len(sql_data)

def epoch_exec_acc(model, batch_size, sql_data, table_data, db_path):
    engine = DBEngine(db_path)

    model.eval()
    perm = list(range(len(sql_data)))
    tot_acc_num = 0.0
    acc_of_log = 0.0
    st = 0
    while st < len(sql_data):
        ed = st+batch_size if st+batch_size < len(perm) else len(perm)
        q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq, raw_data = \
            to_batch_seq(sql_data, table_data, perm, st, ed, ret_vis_data=True)
        raw_q_seq = [x[0] for x in raw_data]
        raw_col_seq = [x[1] for x in raw_data]
        gt_where_seq = model.generate_gt_where_seq(q_seq, col_seq, query_seq)
        query_gt, table_ids = to_batch_query(sql_data, perm, st, ed)
        gt_sel_seq = [x[1] for x in ans_seq]
        score = model.forward(q_seq, col_seq, col_num,
                (True, True, True), gt_sel=gt_sel_seq)
        pred_queries = model.gen_query(score, q_seq, col_seq,
                raw_q_seq, raw_col_seq, (True, True, True))

        for idx, (sql_gt, sql_pred, tid) in enumerate(
                zip(query_gt, pred_queries, table_ids)):
            ret_gt = engine.execute(tid,
                    sql_gt['sel'], sql_gt['agg'], sql_gt['conds'])
            try:
                ret_pred = engine.execute(tid,
                        sql_pred['sel'], sql_pred['agg'], sql_pred['conds'])
            except:
                ret_pred = None
            tot_acc_num += (ret_gt == ret_pred)
        
        st = ed

    return tot_acc_num / len(sql_data)

def epoch_acc_new(model, batch_size, sql_data, table_data, pred_entry):
    model.eval()
    perm = list(range(len(sql_data)))
    st = 0
    one_acc_num = 0.0
    tot_acc_num = 0.0
    while st < len(sql_data):
        ed = st+batch_size if st+batch_size < len(perm) else len(perm)
        q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq, raw_data = to_batch_seq(sql_data, table_data, perm, st, ed, ret_vis_data=True)
        #print ('q_seq ', q_seq)
        raw_q_seq = [x[0] for x in raw_data]
        raw_col_seq = [x[1] for x in raw_data]
        query_gt, table_ids = to_batch_query(sql_data, perm, st, ed)
        gt_sel_seq = [x[1] for x in ans_seq]
        score = model.forward(q_seq, col_seq, col_num,
                pred_entry, gt_sel = gt_sel_seq)
        pred_queries = model.gen_query(score, q_seq, col_seq,
                raw_q_seq, raw_col_seq, pred_entry)
        one_err, tot_err = model.check_acc(raw_data,
                pred_queries, query_gt, pred_entry)

        one_acc_num += (ed-st-one_err)
        tot_acc_num += (ed-st-tot_err)

        st = ed
    return tot_acc_num / len(sql_data), one_acc_num / len(sql_data)
def epoch_acc(model, batch_size, sql_data, table_data, pred_entry):
    print 'epoch_acc_new'
    model.eval()
    perm = list(range(len(sql_data)))
    st = 0
    one_acc_num = 0.0
    tot_acc_num = 0.0
    while st < len(sql_data):
        ed = st+batch_size if st+batch_size < len(perm) else len(perm)
        print('ed is ', ed)
        q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq, raw_data = to_batch_seq(sql_data, table_data, perm, st, ed, ret_vis_data=True)
        print ('q_seq ', q_seq)
        raw_q_seq = [x[0] for x in raw_data]
        raw_col_seq = [x[1] for x in raw_data]
        query_gt, table_ids = to_batch_query(sql_data, perm, st, ed)
        gt_sel_seq = [x[1] for x in ans_seq]
        score = model.forward(q_seq, col_seq, col_num,
                pred_entry, gt_sel = gt_sel_seq)
        pred_queries = model.gen_query(score, q_seq, col_seq,
                raw_q_seq, raw_col_seq, pred_entry)
        one_err, tot_err = model.check_acc(raw_data,
                pred_queries, query_gt, pred_entry)

        one_acc_num += (ed-st-one_err)
        tot_acc_num += (ed-st-tot_err)

        st = ed
    return tot_acc_num / len(sql_data), one_acc_num / len(sql_data)

def epoch_reinforce_train(model, optimizer, batch_size, sql_data, table_data, db_path):
    engine = DBEngine(db_path)

    model.train()
    perm = np.random.permutation(len(sql_data))
    cum_reward = 0.0
    st = 0
    while st < len(sql_data):
        ed = st+batch_size if st+batch_size < len(perm) else len(perm)

        q_seq, col_seq, col_num, ans_seq, query_seq, gt_cond_seq, raw_data =\
            to_batch_seq(sql_data, table_data, perm, st, ed, ret_vis_data=True)
        gt_where_seq = model.generate_gt_where_seq(q_seq, col_seq, query_seq)
        raw_q_seq = [x[0] for x in raw_data]
        raw_col_seq = [x[1] for x in raw_data]
        query_gt, table_ids = to_batch_query(sql_data, perm, st, ed)
        gt_sel_seq = [x[1] for x in ans_seq]
        score = model.forward(q_seq, col_seq, col_num, (True, True, True),
                reinforce=True, gt_sel=gt_sel_seq)
        pred_queries = model.gen_query(score, q_seq, col_seq, raw_q_seq,
                raw_col_seq, (True, True, True), reinforce=True)

        query_gt, table_ids = to_batch_query(sql_data, perm, st, ed)
        rewards = []
        for idx, (sql_gt, sql_pred, tid) in enumerate(
                zip(query_gt, pred_queries, table_ids)):
            ret_gt = engine.execute(tid,
                    sql_gt['sel'], sql_gt['agg'], sql_gt['conds'])
            try:
                ret_pred = engine.execute(tid,
                        sql_pred['sel'], sql_pred['agg'], sql_pred['conds'])
            except:
                ret_pred = None

            if ret_pred is None:
                rewards.append(-2)
            elif ret_pred != ret_gt:
                rewards.append(-1)
            else:
                rewards.append(1)

        cum_reward += (sum(rewards))
        optimizer.zero_grad()
        model.reinforce_backward(score, rewards)
        optimizer.step()

        st = ed

    return cum_reward / len(sql_data)


def load_word_emb(file_name, load_used=False, use_small=False):
    if not load_used:
        print ('Loading word embedding from %s'%file_name)
        ret = {}
        with open(file_name) as inf:
            for idx, line in enumerate(inf):
                if (use_small and idx >= 5000):
                    break
                info = line.strip().split(' ')
                if info[0].lower() not in ret:
                    ret[info[0]] = np.array(map(lambda x:float(x), info[1:]))
        return ret
    else:
        print ('Load used word embedding')
        with open('glove/word2idx.json') as inf:
            w2i = json.load(inf)
        with open('glove/usedwordemb.npy') as inf:
            word_emb_val = np.load(inf)
        return w2i, word_emb_val
