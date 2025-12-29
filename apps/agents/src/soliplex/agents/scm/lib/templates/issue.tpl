{#
  template for rendering an issue with comments
#}
# {{ issue.title }}  Issue#{{ issue.number }} for {{ owner }}/{{ repo }}      
created by {{ issue.user.login }} on {{ issue.created_at }} state={{ issue.state }}      
{% if issue.assignee is defined %}
  assigned to: {{ issue.assignee.login }}
{% endif %}  
{{ issue.body }}
## Comments                               
{% for comment in issue.comments %}
-comment by {{ comment.user }} on {{ comment.created_at }}
{{ comment.body }}
{% endfor %}
