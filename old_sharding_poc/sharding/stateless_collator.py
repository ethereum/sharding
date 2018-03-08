from ethereum.slogging import get_logger

from sharding.validator_manager_utils import call_valmgr

log = get_logger('sharding.collator')


def get_collations_with_score(main_state, shard_id, score):
    """ Get collations with the given shard_id and score

    TODO: cache result
    """
    return [
        call_valmgr(
            main_state,
            'get_collations_with_score',
            [shard_id, score, i],
        ) for i in range(
            call_valmgr(
                main_state,
                'get_num_collations_with_score',
                [shard_id, score],
            )
        )
    ]


def get_collations_with_scores_in_range(main_state, shard_id, low, high):
    """ Get collations with the given shard_id and the score within the certain range
    """
    o = []
    for i in range(low, high+1):
        o.extend(
            get_collations_with_score(
                main_state,
                shard_id,
                i,
            )
        )
    return o
