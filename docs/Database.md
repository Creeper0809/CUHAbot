
Table "Item_Ability" {

  "id" int [pk, not null, increment]

  "item_id" int [not null, default: "0"]

  "ability_id" int [not null, default: "0"]


Indexes {

  item_id [name: "FK_item_ability_tablI_item"]

}

}


Table "Ability_Table"{

  id int [pk,increment]

  name varchar

  description varchar

}


Table "Consumeable_Item" {

  "id" int [pk, not null, increment]

  "amount" int [default: NULL]

}


Table "Droptable" {

  "id" int [pk, not null, increment]

  "drop_monster" int [default: NULL]

  "probability" float [default: NULL,note:"설명"]

  "item_id" int [default: NULL]


Indexes {

  drop_monster [name: "drop_monster"]

  item_id [name: "FK_Droptable_item"]

}

}


Table "Dungeon_info" {

  "id" int [pk]

  "name" varchar(50) [unique, not null, default: ""]

  "min_level" int [not null, default: "0"]

  "description" varchar(50) [not null, default: ""]

}


Table "Encounter" {

"id" int [pk, not null, increment]

"dungeon_id" int [not null]

"encounter_type" varchar(50) [not null]

"encounter_value" varchar(50) [not null]

"probability" float [not null, default: "0"]

}

Table "Lootbox" {

"id" int [pk, not null, increment]

"box_name" varchar(50) [not null]

"description" varchar

"spawn_dungeon" int(50) [default: NULL]

}


Table "Loot" {

"id" int [pk, not null, increment]

"box_id" int [not null]

"loot_type" enum('item', 'consumable') [not null]

"probability" float [default: NULL]

}

Table "Grade"{

  id int [pk]

  name varchar

  description varchar

}

Table "ItemGradeProbability" {

"id" int [pk, not null, increment]

"chest_id" int [not null]

"grade" enum('S', 'A', 'B', 'C', 'D') [default: NULL]

"probability" float [not null]

}

Table "DungeonItem" {

"id" int [pk, not null, increment]

"item_id" int [not null]

"dungeon_id" int(50) [not null]

"amount" int

}

Table "Equipment_Item" {

  "id" int [pk, not null]

  "attack" int [default: NULL]

  "hp" int [default: NULL]

  "ap_attack" int [default: NULL]

  "ad_defense" int [default: NULL]

  "ap_defense" int [default: NULL]

  "grade" int [default: NULL]

  "equip_pos" int

}


Table "Require_Experiment" {

  "level" int [pk, not null, increment]

  "required_experience" int [default: NULL]

  "accumulated_experience" int [default: NULL]

}


Table "item" {

  "id" int [pk, not null]

  "name" varchar(50) [default: NULL]

  "description" varchar(50) [default: NULL]

  "image_link" text

  "cost" int

  "emoji_id" text

  "type" enum('consume', 'equip', 'skill')

}


Table "Monster" {

  "id" int [pk, not null, increment]

  "name" varchar(50) [not null, default: "0"]

  "type" enum('CommonMob','EliteMob','BossMob','RadeMob')

  "level" int [default: NULL]

  "dropPWN" int [default: NULL]

  "hp" int [default: NULL]

  "attack" int [default: NULL]

  "defense" int [not null, default: "0"]

  "speed" int [not null, default: "0"]

  "dungeon" int [default: NULL]

  "skill" text

  "passive" text


Indexes {

  dungeon [name: "FK_Monster_Dungeon_info"]

}

}

Table "RadeMob"{

  id int [pk]

  use_pattern int

}

Table "Pattern"{

  id int [pk]

  name varchar

}

Table "User" {

  "id" int [pk, not null]

  "user_id" varchar

  "discord_id" varchar

  "email" varchar(50)

  "password" varchar(50)

  "comment" varchar(50)

  "discord_name" varchar(50) [default: NULL]

  "CUHA_point" bigint(19)

  "baekjoon_id" varchar(50) [default: NULL]

  "attendance_check" date [not null]

  "register_date" date

}

Table "ProblemList"{

  "id" int [pk]

  "name" varchar

  "author" varchar

  "point" int

  "flag" varchar

}

Table "UserSolvedProblem"{

  "id" int [pk]

  "user_id" varchar

  "problem_id" int

}

Table "User_Inv" {

  "id" bigint [pk, not null, increment]

  "item_id" int [default: NULL]

  "discord_id" varchar(50) [default: NULL]

  "quantity" bigint [default: NULL]


Indexes {

  discord_id [name: "FK_User_Inv_UserRPGInfo"]

  item_id [type: btree, name: "FK_User_Inv_item"]

}

}


Table "UserSpec" {

  "id" varchar(50) [pk,not null]

  "name" varchar(50) [default: NULL]

  "level" int [default: NULL]

  "accumulated_exp" int [default: NULL]

  "hp" bigint [not null, default: "0"]

  "now_hp" bigint [default: NULL]

  "attack" bigint [not null, default: "0"]

  "accuracy" int [default: NULL]

  "defense" bigint [not null, default: "0"]

  "speed" bigint [not null, default: "0"]

Indexes {

  id [type: btree, name: "discord_id"]

}

}


Table "Rade"{

  id int [pk]

  moster_id id

  spawned_time date

  now_hp float

}

Table "User_eq_inv" {

  "id" int [pk, not null, increment]

  "inv_id" int [not null, default: "0"]

  "slot" int [default: NULL]

Indexes {

  inv_id [name: "FK_User_eq_inv_item"]

}

}


Table "Enhancement_Scroll"{

  "id" int [pk,increment]

  "plus_attack" int

  "plus_hp" int

  "plus_defense" int

  "plus_ap_attack" int

  "plus_ability" varchar

  "probability" float

}

Table "Auction"{

  id int [pk]

  discord_id varchar

  inv_id int

  cost int

 

}

Table "Enhancement_Scroll_Avaliable_Pos"{

  id int [pk]

  equip_pos_id int

  scroll_id int

}

Table "Enhanced_Equipment"{

  "id" varchar [pk]

  "inv_id" int

  "scroll_id" int

  "how_many_used" int

}


Table "EquipPos"{

  id int [pk]

  pos_name varchar

  description varchar

}

Ref "FK_item_ability_tablI_item":"item"."id" < "Item_Ability"."item_id"


Ref "FK_Consumeable_Item_item":"item"."id" < "Consumeable_Item"."id"


Ref "FK_Droptable_item":"item"."id" < "Droptable"."item_id"


Ref "FK_Droptable_Monster":"Monster"."id" < "Droptable"."drop_monster"


Ref "FK_Equipment_Item_item":"item"."id" < "Equipment_Item"."id"


Ref "FK_User_Inv_item":"item"."id" < "User_Inv"."item_id"


Ref "FK_User_Inv_UserSpec":"UserSpec"."id" < "User_Inv"."discord_id"


Ref: "User"."id" - "UserSpec"."id"


Ref: "EquipPos"."id" < "Equipment_Item"."equip_pos"


Ref: "EquipPos"."id" < "Enhancement_Scroll_Avaliable_Pos"."equip_pos_id"


Ref: "Enhancement_Scroll"."id" < "Enhancement_Scroll_Avaliable_Pos"."scroll_id"


Ref: "Dungeon_info"."id" < "Encounter"."dungeon_id"


Ref: "Dungeon_info"."id" < "Monster"."dungeon"


Ref: "Dungeon_info"."id" < "Lootbox"."spawn_dungeon"


Ref: "Dungeon_info"."id" < "DungeonItem"."dungeon_id"


Ref: "Lootbox"."id" < "Loot"."box_id"


Ref: "Lootbox"."id" < "ItemGradeProbability"."chest_id"


Ref: "ItemGradeProbability"."grade" > "Grade"."id"


Ref: "Grade"."id" < "Equipment_Item"."grade"


Ref: "item"."id" < "DungeonItem"."item_id"


Ref: "User_Inv"."id" < "User_eq_inv"."inv_id"


Ref: "User_Inv"."id" < "Enhanced_Equipment"."inv_id"


Ref: "Ability_Table"."id" < "Item_Ability"."ability_id"


Ref: "Ability_Table"."id" < "Enhancement_Scroll"."plus_ability"


Ref: "item"."id" < "Enhancement_Scroll"."id"


Ref: "Enhancement_Scroll"."id" < "Enhanced_Equipment"."scroll_id"


Ref: "User_Inv"."id" < "Auction"."inv_id"


Ref: "User_Inv"."id" < "Auction"."discord_id"


Ref: "Monster"."id" < "Rade"."moster_id"


Ref: "RadeMob"."id" > "Monster"."id"



Ref: "Pattern"."id" < "RadeMob"."use_pattern"


Ref: "User"."id" < "UserSolvedProblem"."user_id"


Ref: "ProblemList"."id" < "UserSolvedProblem"."problem_id" 