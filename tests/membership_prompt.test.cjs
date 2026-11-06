const {test}=require('node:test');const assert=require('node:assert/strict');
const load=()=>import('../stylist/static/closet-app/points-earning.js');
for(const [label,vip,action] of [
 ['unread',null,'查看会员'],['invalid flag',{is_vip:'true'},'查看会员'],
 ['nonmember',{is_vip:false},'去开通'],['expired',{is_vip:0,vip_type:3},'去开通'],
 ['active member',{is_vip:true,vip_type:3},'去续费'],['numeric active',{is_vip:1,vip_type:2},'去续费'],
 ['lifetime',{is_vip:true,vip_type:1,is_lifetime_vip:true},'查看权益'],
 ['legacy lifetime',{is_vip:true,vip_type:5},'查看权益'],
 ['both timed and lifetime',{is_vip:true,vip_type:3,is_lifetime_vip:true},'去续费']
])test(label+' gets the correct membership action',async()=>{const {membershipPrompt}=await load();assert.equal(membershipPrompt(vip?{vip_info:vip}:null).action,action);});
