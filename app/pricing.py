from .config import DEFAULT_MARKUP_RUPEES,RARE_MARKUP_RUPEES,RARE_COST_MAX_RUPEES
def sell_price(cost_rupees:float)->float:
    markup=RARE_MARKUP_RUPEES if cost_rupees<=RARE_COST_MAX_RUPEES else DEFAULT_MARKUP_RUPEES
    return round(cost_rupees+markup,2)
