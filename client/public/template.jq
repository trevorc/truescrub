(
  .outputs 
  | to_entries[] 
  | select(.key | endswith(".js")) 
  | select(.value.entryPoint) 
  | .key 
  | split("/")[-1]
) as $js |

(
  .outputs 
  | keys_unsorted[] 
  | select(endswith(".css")) 
  | split("/")[-1]
) as $css |

$template 
| gsub("{{JS_BUNDLE}}"; $js) 
| gsub("{{CSS_BUNDLE}}"; $css)
